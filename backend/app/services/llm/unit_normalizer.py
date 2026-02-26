import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    UNIT_CONVERSION_ONTOLOGY,
    UNIT_NORMALIZE_PROMPT_VERSION,
    UNIT_NORMALIZE_TEMPLATE,
)


class UnitNormalizeSignature(dspy.Signature):
    """Normalize ingredient quantities using explicit conversion ontology."""

    ingredient_text: str = dspy.InputField()
    conversion_ontology: str = dspy.InputField()
    prompt_template: str = dspy.InputField()
    base_unit: str = dspy.OutputField(desc="canonical unit such as g, ml, count")
    base_unit_qty: float = dspy.OutputField(desc="base unit quantity for 1 unit")
    normalized_qty: float = dspy.OutputField(
        desc="quantity of ingredient in base units for this recipe line"
    )
    normalized_unit: str = dspy.OutputField(desc="same as base_unit")


class UnitNormalizer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(UnitNormalizeSignature)

    def forward(self, ingredient_text: str) -> dspy.Prediction:
        return self.predict(
            ingredient_text=ingredient_text,
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


def normalize_units(ingredient_text: str) -> dict:
    key = ingredient_text.strip().lower()
    if key in _units_cache:
        return _units_cache[key].copy()
    normalizer = UnitNormalizer()
    prediction = run_with_logging(
        prompt_name="unit_normalize",
        prompt_version=UNIT_NORMALIZE_PROMPT_VERSION,
        fn=normalizer.forward,
        ingredient_text=ingredient_text,
    )
    out = {
        "base_unit": _strip_prefix(prediction.base_unit) or "count",
        "base_unit_qty": _parse_float(prediction.base_unit_qty),
        "normalized_qty": _parse_float(prediction.normalized_qty),
        "normalized_unit": _strip_prefix(prediction.normalized_unit) or _strip_prefix(prediction.base_unit) or "count",
    }
    if len(_units_cache) < _UNITS_CACHE_MAX:
        _units_cache[key] = out.copy()
    return out


def _parse_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return 0.0
    text = str(value)
    match = __import__("re").search(r"([\d\.]+)", text)
    if not match:
        return 0.0
    return float(match.group(1))
