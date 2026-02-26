"""
Convert SKU size string to quantity in ingredient base unit.
Two LLM passes: (1) reason about conversions, (2) produce quantity and display.
No regex, no pattern matching, no cream fix.
"""

from typing import Tuple

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    SKU_SIZE_EXTRACT_PROMPT_VERSION,
    SKU_SIZE_PRODUCE_TEMPLATE,
    SKU_SIZE_REASON_TEMPLATE,
    UNIT_CONVERSION_ONTOLOGY,
)


class SKUReasonSignature(dspy.Signature):
    """Reason about how to convert SKU size to base unit quantity."""

    size_string: str = dspy.InputField()
    product_name: str = dspy.InputField()
    base_unit: str = dspy.InputField()
    prompt: str = dspy.InputField()
    reasoning: str = dspy.OutputField(desc="step-by-step conversion reasoning")


class SKUProduceSignature(dspy.Signature):
    """Produce quantity and size_display from reasoning."""

    size_string: str = dspy.InputField()
    product_name: str = dspy.InputField()
    base_unit: str = dspy.InputField()
    reasoning: str = dspy.InputField()
    prompt: str = dspy.InputField()
    quantity_in_base_unit: float = dspy.OutputField()
    size_display: str = dspy.OutputField()


def convert_sku_size(size_string: str | None, base_unit: str, product_name: str | None = None) -> Tuple[float, str]:
    """Two-pass LLM: reason first, then produce."""
    size_string = (size_string or "").strip() or "each"
    product_name = (product_name or "").strip()
    base_unit = (base_unit or "count").strip().lower()
    if base_unit not in ("g", "ml", "count", "tbsp", "tsp"):
        base_unit = "count"

    # Pass 1: reason
    reason_prompt = SKU_SIZE_REASON_TEMPLATE.format(
        conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
    )
    reason_predictor = dspy.Predict(SKUReasonSignature)
    reason_pred = run_with_logging(
        prompt_name="sku_size_reason",
        prompt_version=SKU_SIZE_EXTRACT_PROMPT_VERSION,
        fn=reason_predictor,
        model="gpt-4o-mini",
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
        prompt=reason_prompt,
    )
    reasoning = str(getattr(reason_pred, "reasoning", "") or "").strip()

    # Pass 2: produce
    produce_prompt = SKU_SIZE_PRODUCE_TEMPLATE.format(
        conversion_ontology=UNIT_CONVERSION_ONTOLOGY,
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
        reasoning=reasoning,
    )
    produce_predictor = dspy.Predict(SKUProduceSignature)
    produce_pred = run_with_logging(
        prompt_name="sku_size_produce",
        prompt_version=SKU_SIZE_EXTRACT_PROMPT_VERSION,
        fn=produce_predictor,
        model="gpt-4o-mini",
        size_string=size_string,
        product_name=product_name,
        base_unit=base_unit,
        reasoning=reasoning,
        prompt=produce_prompt,
    )

    try:
        qty = float(getattr(produce_pred, "quantity_in_base_unit", 1.0) or 1.0)
    except (TypeError, ValueError):
        qty = 1.0
    if qty <= 0:
        qty = 1.0

    display = str(getattr(produce_pred, "size_display", "") or size_string).strip()
    return qty, display
