import re

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.ingredient_ontology import get_preferred_base_unit
from app.services.llm.prompts import (
    UNIT_CONVERSION_ONTOLOGY,
    UNIT_NORMALIZE_PROMPT_VERSION,
    UNIT_NORMALIZE_TEMPLATE,
)


class UnitNormalizeSignature(dspy.Signature):
    """Normalize ingredient quantities to target base unit using conversion ontology."""

    ingredient_text: str = dspy.InputField()
    canonical_name: str = dspy.InputField(desc="target ingredient for shopping")
    target_base_unit: str = dspy.InputField(desc="convert output to this unit: g, ml, count, tbsp, tsp")
    conversion_ontology: str = dspy.InputField()
    prompt_template: str = dspy.InputField()
    base_unit: str = dspy.OutputField(desc="same as target_base_unit")
    base_unit_qty: float = dspy.OutputField(desc="base unit quantity for 1 unit")
    normalized_qty: float = dspy.OutputField(
        desc="quantity of ingredient in base units for this recipe line"
    )
    normalized_unit: str = dspy.OutputField(desc="same as base_unit")


class UnitNormalizer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(UnitNormalizeSignature)

    def forward(
        self,
        ingredient_text: str,
        canonical_name: str = "",
        target_base_unit: str = "",
    ) -> dspy.Prediction:
        return self.predict(
            ingredient_text=ingredient_text,
            canonical_name=canonical_name or "unknown",
            target_base_unit=target_base_unit or "count",
            conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
            prompt_template=UNIT_NORMALIZE_TEMPLATE,
        )


def _strip_prefix(val: str | None, prefixes: tuple[str, ...] = ("Base Unit:", "Normalized Qty:", "Base Unit Qty:", "Normalized Unit:")) -> str:
    if not val:
        return ""
    s = str(val).strip()
    for p in prefixes:
        if s.lower().startswith(p.lower()):
            s = s[len(p):].strip()
    return s


_units_cache: dict[str, dict] = {}
_UNITS_CACHE_MAX = 500


_CANONICAL_BASE_UNITS = frozenset({"g", "ml", "count", "tbsp", "tsp"})


def _sanitize_base_unit(val: str | None) -> str:
    """Extract only the canonical base unit; strip any extra LLM text."""
    s = _strip_prefix(val) or ""
    s = s.strip().lower()
    # Take first word before space/paren
    first = s.split()[0] if s else ""
    first = first.split("(")[0].split(",")[0].strip()
    return first if first in _CANONICAL_BASE_UNITS else "count"


def _deterministic_normalize(text: str, canonical: str, target: str) -> dict | None:
    """Try to convert without LLM. Returns None if ambiguous."""
    t = (text or "").strip().lower()
    c = (canonical or "").lower()
    if not t or "to taste" in t or "pinch" in t or "salt and pepper" in t:
        return {"base_unit": target, "base_unit_qty": 1.0, "normalized_qty": 0.0, "normalized_unit": target}
    # Count: "4 cloves garlic", "2 lemons"
    if m := re.search(r"([\d\.]+)\s*(?:cloves?|heads?)\s+(?:garlic|minced)", t):
        if target == "count":
            return {"base_unit": "count", "base_unit_qty": 1.0, "normalized_qty": float(m.group(1)), "normalized_unit": "count"}
    if m := re.match(r"([\d\.]+)\s*(?:lemons?|limes?|oranges?|eggs?|apples?)\b", t):
        if target == "count":
            return {"base_unit": "count", "base_unit_qty": 1.0, "normalized_qty": float(m.group(1)), "normalized_unit": "count"}
    # Volume to ml: "1/2 cup", "2 cups", "1/4 cup", "2 tablespoons"
    if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*cups?\b", t):
        whole = float(m.group(1))
        frac = float(m.group(2)) if m.group(2) else 1
        cups = whole / frac if m.group(2) else whole
        ml = cups * 240
        if target == "ml":
            return {"base_unit": "ml", "base_unit_qty": 1.0, "normalized_qty": round(ml, 1), "normalized_unit": "ml"}
    if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*tablespoons?\b", t):
        whole = float(m.group(1))
        frac = float(m.group(2)) if m.group(2) else 1
        tbsp = whole / frac if m.group(2) else whole
        if target == "tbsp":
            return {"base_unit": "tbsp", "base_unit_qty": 1.0, "normalized_qty": round(tbsp, 1), "normalized_unit": "tbsp"}
        if target == "ml":
            return {"base_unit": "ml", "base_unit_qty": 1.0, "normalized_qty": round(tbsp * 15, 1), "normalized_unit": "ml"}
    if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*teaspoons?\b", t):
        whole = float(m.group(1))
        frac = float(m.group(2)) if m.group(2) else 1
        tsp = whole / frac if m.group(2) else whole
        if target == "tsp":
            return {"base_unit": "tsp", "base_unit_qty": 1.0, "normalized_qty": round(tsp, 1), "normalized_unit": "tsp"}
        if target == "tbsp":
            return {"base_unit": "tbsp", "base_unit_qty": 1.0, "normalized_qty": round(tsp / 3, 2), "normalized_unit": "tbsp"}
    # Weight to g: "2 lbs", "4 lb", "1/2 oz"
    if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*(?:lb|pound)s?\b", t):
        whole = float(m.group(1))
        frac = float(m.group(2)) if m.group(2) else 1
        lb = whole / frac if m.group(2) else whole
        g = lb * 453.59
        if target == "g":
            return {"base_unit": "g", "base_unit_qty": 1.0, "normalized_qty": round(g, 2), "normalized_unit": "g"}
    if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*oz\b(?!\s*fl)", t):
        whole = float(m.group(1))
        frac = float(m.group(2)) if m.group(2) else 1
        oz = whole / frac if m.group(2) else whole
        g = oz * 28.35
        if target == "g":
            return {"base_unit": "g", "base_unit_qty": 1.0, "normalized_qty": round(g, 2), "normalized_unit": "g"}
    # Lemon juice → count: "1 tablespoon lemon juice" with lemon
    if "lemon juice" in t or "lime juice" in t:
        if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*tablespoons?\b", t):
            whole = float(m.group(1))
            frac = float(m.group(2)) if m.group(2) else 1
            tbsp = whole / frac if m.group(2) else whole
            if target == "count" and ("lemon" in c or "lime" in c):
                return {"base_unit": "count", "base_unit_qty": 1.0, "normalized_qty": round(tbsp / 3, 2), "normalized_unit": "count"}
    # Butter: "4 tablespoons butter" -> 56g (1 tbsp ≈ 14g)
    if ("butter" in t or "butter" in c) and target == "g":
        if m := re.search(r"([\d\.]+)\s*(?:/\s*)?(\d+)?\s*tablespoons?\b", t):
            whole, frac = float(m.group(1)), (float(m.group(2)) if m.group(2) else 1)
            tbsp = whole / frac
            return {"base_unit": "g", "base_unit_qty": 1.0, "normalized_qty": round(tbsp * 14, 1), "normalized_unit": "g"}
        if m := re.search(r"([\d\.]+)\s*sticks?\b", t):
            tbsp = float(m.group(1)) * 8
            return {"base_unit": "g", "base_unit_qty": 1.0, "normalized_qty": round(tbsp * 14, 1), "normalized_unit": "g"}
    return None


def normalize_units(
    ingredient_text: str,
    canonical_name: str = "",
    target_base_unit: str | None = None,
) -> dict:
    target = target_base_unit or get_preferred_base_unit(canonical_name)
    key = f"{UNIT_NORMALIZE_PROMPT_VERSION}:{target}:{canonical_name.strip().lower()}:{ingredient_text.strip().lower()}"
    if key in _units_cache:
        return _units_cache[key].copy()
    det = _deterministic_normalize(ingredient_text, canonical_name, target)
    if det:
        if len(_units_cache) < _UNITS_CACHE_MAX:
            _units_cache[key] = det.copy()
        return det.copy()
    normalizer = UnitNormalizer()
    prediction = run_with_logging(
        prompt_name="unit_normalize",
        prompt_version=UNIT_NORMALIZE_PROMPT_VERSION,
        fn=normalizer.forward,
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
        target_base_unit=target,
    )
    base = _sanitize_base_unit(prediction.base_unit) or target
    out = {
        "base_unit": base,
        "base_unit_qty": _parse_float(prediction.base_unit_qty),
        "normalized_qty": _parse_float(prediction.normalized_qty),
        "normalized_unit": base,
    }
    if len(_units_cache) < _UNITS_CACHE_MAX:
        _units_cache[key] = out.copy()
    return out


def _parse_float(value: object) -> float:
    """Extract the main quantity from LLM output."""
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return 0.0
    text = str(value).strip()
    for prefix in ("normalized qty:", "normalized_qty:", "quantity:"):
        idx = text.lower().find(prefix)
        if idx >= 0:
            rest = text[idx + len(prefix):].strip()
            m = re.search(r"([\d\.]+)", rest)
            if m:
                return float(m.group(1))
    m = re.search(r"([\d\.]+)", text)
    return float(m.group(1)) if m else 0.0
