"""
Normalize ingredient quantities to a canonical base unit.
Two LLM passes: (1) reason about conversions, (2) produce normalized quantities.
LLM selects base_unit per explicit rules (liquids→ml, butter→g, countable→count, etc.).
"""

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    UNIT_CONVERSION_ONTOLOGY,
    UNIT_NORMALIZE_PROMPT_VERSION,
    UNIT_NORMALIZE_PRODUCE_TEMPLATE,
    UNIT_NORMALIZE_REASON_TEMPLATE,
)


class ReasonSignature(dspy.Signature):
    """Reason about how to convert ingredient quantity to canonical base unit."""

    ingredient_text: str = dspy.InputField()
    canonical_name: str = dspy.InputField()
    prompt: str = dspy.InputField()
    reasoning: str = dspy.OutputField(desc="step-by-step conversion reasoning")


class ProduceSignature(dspy.Signature):
    """Produce normalized quantities from reasoning."""

    ingredient_text: str = dspy.InputField()
    canonical_name: str = dspy.InputField()
    reasoning: str = dspy.InputField()
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
    """Two-pass LLM: reason first, then produce. LLM selects base_unit per explicit rules."""
    # Pass 1: reason
    reason_prompt = UNIT_NORMALIZE_REASON_TEMPLATE.format(
        conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
    )
    reason_predictor = dspy.Predict(ReasonSignature)
    reason_pred = run_with_logging(
        prompt_name="unit_normalize_reason",
        prompt_version=UNIT_NORMALIZE_PROMPT_VERSION,
        fn=reason_predictor,
        model="gpt-4o-mini",
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
        prompt=reason_prompt,
    )
    reasoning = str(getattr(reason_pred, "reasoning", "") or "").strip()

    # Pass 2: produce
    produce_prompt = UNIT_NORMALIZE_PRODUCE_TEMPLATE.format(
        conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
        reasoning=reasoning,
    )
    produce_predictor = dspy.Predict(ProduceSignature)
    produce_pred = run_with_logging(
        prompt_name="unit_normalize_produce",
        prompt_version=UNIT_NORMALIZE_PROMPT_VERSION,
        fn=produce_predictor,
        model="gpt-4o-mini",
        ingredient_text=ingredient_text,
        canonical_name=canonical_name or "unknown",
        reasoning=reasoning,
        prompt=produce_prompt,
    )

    base = str(getattr(produce_pred, "base_unit", "") or target_base_unit or "count").strip().lower().split()[0]
    if base not in ("g", "ml", "count", "tbsp", "tsp"):
        base = target_base_unit if target_base_unit else "count"

    try:
        base_qty = float(getattr(produce_pred, "base_unit_qty", 1.0) or 1.0)
    except (TypeError, ValueError):
        base_qty = 1.0

    try:
        norm_qty = float(getattr(produce_pred, "normalized_qty", 0) or 0)
    except (TypeError, ValueError):
        norm_qty = 0.0

    norm_unit = str(getattr(produce_pred, "normalized_unit", "") or base).strip().lower().split()[0]
    if norm_unit not in ("g", "ml", "count", "tbsp", "tsp"):
        norm_unit = base

    return {
        "base_unit": base,
        "base_unit_qty": base_qty,
        "normalized_qty": norm_qty,
        "normalized_unit": norm_unit,
    }
