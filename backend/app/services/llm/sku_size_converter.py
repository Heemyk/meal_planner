"""
Convert SKU size string to quantity in ingredient base unit.
Single LLM pass: convert directly to quantity_in_base_unit and size_display.
"""

import re
from typing import Tuple

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    SKU_SIZE_EXTRACT_PROMPT_VERSION,
    SKU_SIZE_TEMPLATE,
    UNIT_CONVERSION_ONTOLOGY,
)


class SKUSizeSignature(dspy.Signature):
    """Convert product size to quantity in base unit."""

    size_string: str = dspy.InputField()
    product_name: str = dspy.InputField()
    base_unit: str = dspy.InputField()
    prompt: str = dspy.InputField()
    quantity_in_base_unit: float = dspy.OutputField()
    size_display: str = dspy.OutputField()


def _effective_size_string(size_string: str, product_name: str) -> str:
    """When size is generic (each/empty), derive from product name so conversion uses actual weight/volume."""
    s = (size_string or "").strip().lower()
    if s and s != "each" and s != "ea":
        return size_string.strip()
    # Product name often embeds size: "Colossal Garlic, 2 lbs", "Pompeian Olive Oil, 68 fl oz"
    extracted = _extract_size_from_product_name(product_name)
    return extracted if extracted else (size_string or "each").strip()


def _extract_size_from_product_name(product_name: str) -> str:
    """Extract weight/volume from product name when Instacart returns size='each'."""
    if not product_name:
        return ""
    # Match: "2 lbs", "68 fl oz", "0.5 oz", "1 lb", "750 ml", "2 L", etc.
    m = re.search(
        r"(\d+\.?\d*)\s*(fl\s*oz|oz|lb|lbs?|kg|g|ml|L)\b",
        product_name,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)} {m.group(2)}".strip()
    return ""


def convert_sku_size(size_string: str | None, base_unit: str, product_name: str | None = None) -> Tuple[float, str]:
    """Single-pass LLM: convert size to quantity_in_base_unit and size_display."""
    product_name = (product_name or "").strip()
    size_string = _effective_size_string((size_string or "").strip() or "each", product_name)
    base_unit = (base_unit or "count").strip().lower()
    if base_unit not in ("g", "ml", "count", "tbsp", "tsp"):
        base_unit = "count"

    prompt = SKU_SIZE_TEMPLATE.format(
        conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
    )
    predictor = dspy.Predict(SKUSizeSignature)
    pred = run_with_logging(
        prompt_name="sku_size",
        prompt_version=SKU_SIZE_EXTRACT_PROMPT_VERSION,
        fn=predictor,
        model="gpt-4o-mini",
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
        prompt=prompt,
    )

    raw_qty = getattr(pred, "quantity_in_base_unit", None)
    qty = _parse_quantity(raw_qty)

    raw = str(getattr(pred, "size_display", "") or size_string).strip()
    display = _sanitize_size_display(raw, size_string, max_len=64)
    return qty, display


def _parse_quantity(raw: object) -> float:
    """Extract numeric quantity; LLM sometimes dumps full prompt into output."""
    if raw is None:
        return 1.0
    try:
        qty = float(raw)
        return max(1.0, qty) if qty > 0 else 1.0
    except (TypeError, ValueError):
        pass
    s = str(raw).strip()
    # Extract from "Quantity In Base Unit: 946" or similar
    for prefix in ("Quantity In Base Unit:", "quantity_in_base_unit:", "quantity:"):
        if prefix.lower() in s.lower():
            idx = s.lower().find(prefix.lower())
            rest = s[idx + len(prefix) :].strip()
            for word in rest.split():
                word = word.rstrip(".,")
                try:
                    qty = float(word)
                    return max(1.0, qty) if qty > 0 else 1.0
                except ValueError:
                    continue
    # Last number in string
    nums = re.findall(r"\d+\.?\d*", s)
    if nums:
        try:
            qty = float(nums[-1])
            return max(1.0, qty) if qty > 0 else 1.0
        except ValueError:
            pass
    return 1.0


def _sanitize_size_display(raw: str, fallback: str, max_len: int = 64) -> str:
    """Strip LLM reasoning leakage and enforce DB length limit."""
    raw = (raw or "").strip()
    if not raw:
        return (fallback or "each")[:max_len]

    # If LLM dumped reasoning: "Size String: 1 lb\n\nProduct Name: ..."
    if "Size String:" in raw:
        m = re.search(r"Size String:\s*([^\n]+)", raw)
        if m:
            raw = m.group(1).strip()
    if "Product Name:" in raw or "Reasoning:" in raw:
        raw = raw.split("\n")[0].strip()
    # Take first line only (size label, not reasoning)
    first_line = raw.split("\n")[0].strip()
    if first_line and len(first_line) <= max_len:
        return first_line
    return (first_line or fallback or "each")[:max_len]
