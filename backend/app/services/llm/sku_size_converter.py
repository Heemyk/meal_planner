"""
Convert SKU size string to quantity in ingredient base unit.
Uses LLM + conversion ontology so LP calculations are correct (e.g. 5 lb → 2267.95 g).
"""

import re
from typing import Tuple

import dspy

from app.services.llm.dspy_client import run_with_reasoning_model
from app.services.llm.prompts import (
    SKU_SIZE_CONVERT_PROMPT_VERSION,
    SKU_SIZE_CONVERT_TEMPLATE,
    UNIT_CONVERSION_ONTOLOGY,
)


class SKUSizeConvertSignature(dspy.Signature):
    """Convert product size to quantity in base unit. Use product_name if size is vague."""

    size_string: str = dspy.InputField(desc="e.g. 5 lb, 32 fl oz, each")
    product_name: str = dspy.InputField(desc="product name; may contain quantity e.g. Olive Oil 2 L")
    base_unit: str = dspy.InputField(desc="target unit: g, ml, count, tbsp, tsp")
    conversion_ontology: str = dspy.InputField()
    prompt_template: str = dspy.InputField()
    quantity_in_base_unit: float = dspy.OutputField(desc="numeric amount in base unit")
    size_display: str = dspy.OutputField(desc="human-friendly e.g. 5 lb")


class SKUSizeConverter(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(SKUSizeConvertSignature)

    def forward(self, size_string: str, base_unit: str, product_name: str = "") -> dspy.Prediction:
        return self.predict(
            size_string=size_string or "each",
            product_name=product_name or "",
            base_unit=base_unit or "count",
            conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
            prompt_template=SKU_SIZE_CONVERT_TEMPLATE,
        )


def _ensure_converted(qty: float, size_string: str, base_unit: str) -> float:
    """If LLM returned raw number (e.g. 5 for '5 lb'), apply conversion when base_unit is g/ml."""
    s = (size_string or "").lower()
    if base_unit == "g":
        if ("lb" in s or "pound" in s) and 0 < qty < 500:
            return qty * 453.59
        if "oz" in s and "fl" not in s and 0 < qty < 1000:
            return qty * 28.35
    if base_unit == "ml":
        if ("fl" in s and "oz" in s) or "fl oz" in s:
            if 0 < qty < 200:
                return qty * 29.57
        if "cup" in s and 0 < qty < 20:
            return qty * 240.0
    return qty


def _parse_float(val: object) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return 1.0
    m = re.search(r"([\d\.]+)", str(val))
    return float(m.group(1)) if m else 1.0


def _parse_display(val: str | None) -> str:
    if not val:
        return ""
    s = str(val).strip()
    for prefix in ("size_display:", "Size Display:", "display:"):
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):].strip()
    return s[:64] if s else ""


def convert_sku_size(size_string: str | None, base_unit: str, product_name: str | None = None) -> Tuple[float, str]:
    """
    Convert SKU size to (quantity_in_base_unit, size_display).
    E.g. ("5 lb", "g") -> (2267.95, "5 lb").
    When size is vague (e.g. "each"), product_name may contain quantity (e.g. "Olive Oil, 2 L").
    Fallback: extract number from size or name, or 1.0 for count.
    """
    size_string = (size_string or "").strip() or "each"
    product_name = (product_name or "").strip()
    try:
        converter = SKUSizeConverter()
        pred = run_with_reasoning_model(
            prompt_name="sku_size_convert",
            prompt_version=SKU_SIZE_CONVERT_PROMPT_VERSION,
            fn=converter.forward,
            size_string=size_string,
            base_unit=base_unit,
            product_name=product_name,
        )
        qty = _parse_float(getattr(pred, "quantity_in_base_unit", 1.0))
        if qty <= 0:
            qty = 1.0
        # Sanity check: LLM may return raw number (5) instead of converted (2267.95 for "5 lb" → g)
        qty = _ensure_converted(qty, size_string, base_unit)
        display = _parse_display(getattr(pred, "size_display", "")) or size_string
        return qty, display
    except Exception as e:
        from app.logging import get_logger
        get_logger(__name__).warning("sku_size_convert.fallback size=%s name=%s base=%s error=%s", size_string, product_name, base_unit, e)
        # Fallback: extract from size first, then from product name
        combined = f"{size_string} {product_name}".strip()
        m = re.search(r"([\d\.]+)\s*(ml|g|lb|oz|fl\s*oz|l|litre)", combined.lower()) or re.search(r"([\d\.]+)", combined)
        num = float(m.group(1)) if m else 1.0
        s_lower = combined.lower()
        if base_unit == "count":
            return num if num > 0 else 1.0, size_string
        # Rough conversions for common cases (check combined size + name)
        if "lb" in s_lower or "pound" in s_lower:
            mult = 453.59 if base_unit == "g" else 1.0
            return num * mult, size_string
        if "oz" in s_lower and "fl" not in s_lower:
            mult = 28.35 if base_unit == "g" else 1.0
            return num * mult, size_string
        if "ml" in s_lower:
            return num if base_unit == "ml" else num, size_string or product_name
        if " l " in s_lower or s_lower.endswith(" l") or "litre" in s_lower:
            return num * 1000 if base_unit == "ml" else num, size_string or product_name
        if "fl" in s_lower:
            mult = 29.57 if base_unit == "ml" else 1.0
            return num * mult, size_string or product_name
        return num, size_string or product_name
