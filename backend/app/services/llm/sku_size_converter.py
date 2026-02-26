"""
Convert SKU size string to quantity in ingredient base unit.
Two-pass: (1) deterministic extraction + conversion when possible, (2) one fast LLM call only when ambiguous.
"""

import re
from typing import Tuple

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    SKU_SIZE_EXTRACT_PROMPT_VERSION,
    SKU_SIZE_EXTRACT_TEMPLATE,
)

# Conversion constants
LB_TO_G = 453.59
OZ_TO_G = 28.35
FL_OZ_TO_ML = 29.57
L_TO_ML = 1000
CUP_TO_ML = 240
TBSP_TO_ML = 15

# Typical weight/volume per "each" for common products (for ambiguous "each" sizes)
_EACH_ESTIMATES_G = {
    "asparagus": 450, "broccoli": 400, "lemon": 70, "lime": 50, "garlic head": 25,
    "garlic": 25, "chicken": 1800, "butter stick": 113,
}
_EACH_ESTIMATES_ML = {
    "cream": 237, "milk": 237, "juice": 355, "oil": 1000,
}


def _is_liquid_product(name: str) -> bool:
    n = (name or "").lower()
    return any(x in n for x in ("cream", "milk", "juice", "oil", "vinegar", "sauce", "dressing", "broth"))


def _deterministic_extract(size_string: str, product_name: str) -> Tuple[float, str, str] | None:
    """Extract (amount, unit, product_hint) from size + name. Returns None if ambiguous."""
    combined = f"{size_string} {product_name}".lower()
    liquid = _is_liquid_product(product_name)
    # Order matters: fl oz before oz
    if m := re.search(r"([\d\.]+)\s*fl\s*oz", combined):
        return float(m.group(1)), "fl_oz", "liquid"
    if m := re.search(r"([\d\.]+)\s*oz(?:\s*,|\s+\d|-count|$)", combined):
        return float(m.group(1)), "fl_oz" if liquid else "oz", "liquid" if liquid else "weight"
    if m := re.search(r"([\d\.]+)\s*(?:lb|pound)s?\b", combined):
        return float(m.group(1)), "lb", "weight"
    if m := re.search(r"([\d\.]+)\s*l(?:itre)?s?\b", combined):
        return float(m.group(1)), "l", "liquid"
    if m := re.search(r"([\d\.]+)\s*ml\b", combined):
        return float(m.group(1)), "ml", "liquid"
    if re.search(r"\b each\b|^\s*each\s*$", size_string.lower()) or (not re.search(r"[\d\.]+\s*(?:lb|oz|ml|l)\b", combined) and "each" in combined):
        return 1.0, "each", _product_hint(product_name)
    return None


def _product_hint(name: str) -> str:
    """Infer product type from name for 'each' conversion."""
    n = (name or "").lower()
    if "cream" in n or "milk" in n or "juice" in n or "oil" in n:
        return "liquid"
    if "asparagus" in n or "broccoli" in n:
        return "asparagus"
    if "garlic" in n:
        return "garlic"
    if "lemon" in n or "lime" in n:
        return "lemon"
    if "chicken" in n:
        return "chicken"
    if "butter" in n:
        return "butter"
    return "unknown"


def _convert_deterministic(amount: float, unit: str, product_hint: str, base_unit: str) -> float:
    """Convert extracted amount to base_unit using fixed conversion factors."""
    if base_unit == "g":
        if unit == "lb":
            return amount * LB_TO_G
        if unit == "oz":
            return amount * OZ_TO_G
        if unit == "each":
            return _EACH_ESTIMATES_G.get(product_hint, 100)
    if base_unit == "ml":
        if unit == "fl_oz":
            return amount * FL_OZ_TO_ML
        if unit == "l":
            return amount * L_TO_ML
        if unit == "ml":
            return amount
        if unit == "each":
            return _EACH_ESTIMATES_ML.get(product_hint, 237)
    if base_unit == "count":
        if unit == "each":
            return amount
        if unit == "lb" and product_hint == "garlic":
            return (amount * LB_TO_G) / 4  # ~4g per clove
    return amount


def _convert_with_llm(size_string: str, product_name: str, base_unit: str) -> Tuple[float, str]:
    """Single fast Predict call (no CoT) when deterministic path fails."""
    from app.services.llm.prompts import SKU_SIZE_EXTRACT_TEMPLATE

    class ExtractSignature(dspy.Signature):
        size_string: str = dspy.InputField()
        product_name: str = dspy.InputField()
        base_unit: str = dspy.InputField()
        prompt_template: str = dspy.InputField()
        quantity_in_base_unit: float = dspy.OutputField(desc="converted to base unit")
        size_display: str = dspy.OutputField(desc="short label e.g. 5 lb")

    predictor = dspy.Predict(ExtractSignature)
    pred = run_with_logging(
        prompt_name="sku_size_extract",
        prompt_version=SKU_SIZE_EXTRACT_PROMPT_VERSION,
        fn=predictor,
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
        prompt_template=SKU_SIZE_EXTRACT_TEMPLATE,
    )
    qty = float(getattr(pred, "quantity_in_base_unit", 1.0) or 1.0)
    if qty <= 0:
        qty = 1.0
    display = _sanitize_display(getattr(pred, "size_display", "") or size_string)
    return qty, display


def _sanitize_display(val: str | None) -> str:
    """Strip LLM leakage (reasoning, prefixes) from size_display."""
    if not val:
        return ""
    s = str(val).strip()
    for prefix in ("size_display:", "Size Display:", "display:", "Final Output:", "Output:"):
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):].strip()
    if "---" in s:
        s = s.split("---")[0].strip()
    if ":" in s and len(s) > 40:
        s = s.split(":")[-1].strip()
    return s[:48].strip() if s else ""


def convert_sku_size(size_string: str | None, base_unit: str, product_name: str | None = None) -> Tuple[float, str]:
    """
    Convert SKU size to (quantity_in_base_unit, size_display).
    Prefer deterministic extraction; use one fast LLM call only when ambiguous.
    """
    size_string = (size_string or "").strip() or "each"
    product_name = (product_name or "").strip()
    base_unit = (base_unit or "count").strip().lower().split()[0].split("(")[0]
    if base_unit not in {"g", "ml", "count", "tbsp", "tsp"}:
        base_unit = "count"

    extracted = _deterministic_extract(size_string, product_name)
    if extracted:
        amount, unit, hint = extracted
        qty = _convert_deterministic(amount, unit, hint, base_unit)
        if qty > 0:
            display = _sanitize_display(size_string) or f"{amount} {unit}"
            return qty, display

    try:
        qty, display = _convert_with_llm(size_string, product_name, base_unit)
        return qty, _sanitize_display(display) or size_string
    except Exception as e:
        from app.logging import get_logger
        get_logger(__name__).warning("sku_size_convert.fallback size=%s name=%s base=%s error=%s", size_string, product_name, base_unit, e)
        combined = f"{size_string} {product_name}".lower()
        m = re.search(r"([\d\.]+)\s*(ml|g|lb|oz|fl\s*oz|l|litre)", combined) or re.search(r"([\d\.]+)", combined)
        num = float(m.group(1)) if m else 1.0
        if base_unit == "count":
            return num if num > 0 else 1.0, _sanitize_display(size_string)
        if "lb" in combined or "pound" in combined:
            return num * LB_TO_G if base_unit == "g" else num, _sanitize_display(size_string)
        if "oz" in combined and "fl" not in combined:
            return num * OZ_TO_G if base_unit == "g" else num, _sanitize_display(size_string)
        if "fl" in combined or "fl oz" in combined:
            return num * FL_OZ_TO_ML if base_unit == "ml" else num, _sanitize_display(size_string)
        if " l " in combined or "litre" in combined:
            return num * L_TO_ML if base_unit == "ml" else num, _sanitize_display(size_string)
        return num, _sanitize_display(size_string)
