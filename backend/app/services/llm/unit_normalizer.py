"""
Normalize ingredient quantities to a canonical base unit.
Single LLM pass: convert directly to base_unit, normalized_qty, normalized_unit.
"""

import re

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    UNIT_CONVERSION_ONTOLOGY,
    UNIT_NORMALIZE_PROMPT_VERSION,
    UNIT_NORMALIZE_TEMPLATE,
)

ALLOWED_BASE_UNITS = ("g", "ml", "count", "tbsp", "tsp")


def _extract_float(raw: object, default: float) -> float:
    """Extract float from LLM output; handles prompt-dump leakage."""
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    s = str(raw).strip()
    for prefix in ("normalized qty:", "normalized_qty:", "base unit qty:", "base_unit_qty:", "quantity:"):
        if prefix in s.lower():
            idx = s.lower().find(prefix)
            rest = s[idx + len(prefix) :].strip()
            for word in rest.split():
                word = word.rstrip(".,")
                try:
                    return float(word)
                except ValueError:
                    continue
    nums = re.findall(r"\d+\.?\d*", s)
    if nums:
        try:
            return float(nums[-1])
        except ValueError:
            pass
    return default


def _extract_base_unit(raw: str) -> str | None:
    """Extract base unit from LLM output; handles prompt-dump leakage."""
    if not raw:
        return None
    s = raw.strip().lower()
    if s in ALLOWED_BASE_UNITS:
        return s
    for prefix in ("base unit:", "base_unit:", "normalized unit:", "normalized_unit:"):
        if prefix in s:
            idx = s.find(prefix)
            rest = s[idx + len(prefix) :].strip()
            for word in rest.split()[:3]:
                w = word.rstrip(".,\n")
                if w in ALLOWED_BASE_UNITS:
                    return w
    for u in ALLOWED_BASE_UNITS:
        if re.search(rf"\b{u}\b", s):
            return u
    return None


class NormalizeSignature(dspy.Signature):
    """Convert recipe ingredient quantity to canonical base unit."""

    ingredient_text: str = dspy.InputField()
    canonical_name: str = dspy.InputField()
    prompt: str = dspy.InputField()
    base_unit: str = dspy.OutputField()
    base_unit_qty: float = dspy.OutputField()
    normalized_qty: float = dspy.OutputField()
    normalized_unit: str = dspy.OutputField()


def normalize_units(
    ingredient_text: str,
    canonical_name: str = "",
    target_base_unit: str | None = None,  # optional override; if None, LLM decides
) -> dict:
    """Single-pass LLM: convert ingredient to base_unit, normalized_qty, normalized_unit."""
    prompt = UNIT_NORMALIZE_TEMPLATE.format(
        conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
    )
    predictor = dspy.Predict(NormalizeSignature)
    pred = run_with_logging(
        prompt_name="unit_normalize",
        prompt_version=UNIT_NORMALIZE_PROMPT_VERSION,
        fn=predictor,
        model="gpt-4o-mini",
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
        prompt=prompt,
    )

    raw_base = str(getattr(pred, "base_unit", "") or target_base_unit or "").strip()
    base = _extract_base_unit(raw_base) or target_base_unit or "count"

    base_qty = _extract_float(getattr(pred, "base_unit_qty", 1.0), 1.0)
    norm_qty = _extract_float(getattr(pred, "normalized_qty", 0), 0.0)

    raw_norm = str(getattr(pred, "normalized_unit", "") or base).strip()
    norm_unit = _extract_base_unit(raw_norm) or base

    return {
        "base_unit": base,
        "base_unit_qty": base_qty,
        "normalized_qty": norm_qty,
        "normalized_unit": norm_unit,
    }
