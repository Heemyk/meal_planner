"""LLM-based correction of anomalous plan results."""

from __future__ import annotations

import json
import re

import dspy

from app.logging import get_logger
from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import OVERSEER_PROMPT_VERSION, OVERSEER_TEMPLATE

logger = get_logger(__name__)


class OverseerSignature(dspy.Signature):
    """Diagnose and correct unit/conversion errors in plan results."""
    prompt: str = dspy.InputField()
    diagnosis: str = dspy.OutputField()
    corrections_json: str = dspy.OutputField()


def run_overseer_correction(
    anomaly: dict,
    ingredient: dict,
    recipe_ingredients: list[dict],
    sku: dict,
) -> list[dict]:
    """
    Call GPT-4o to diagnose anomaly and return corrections.
    Returns list of {"type": str, "id": int, **kwargs} to apply.
    """
    ri_blob = "\n".join(
        f"  id={r.get('id')} recipe_id={r['recipe_id']} recipe={r['recipe_name']} quantity={r['quantity']} unit={r['unit']} original={r.get('original_text','')}"
        for r in recipe_ingredients
    )
    prompt = OVERSEER_TEMPLATE.format(
        reason=anomaly.get("reason", ""),
        ingredient_name=ingredient.get("canonical_name", ""),
        ingredient_id=ingredient.get("id", ""),
        base_unit=ingredient.get("base_unit", ""),
        base_unit_qty=ingredient.get("base_unit_qty", 1),
        recipe_ingredients_blob=ri_blob or "  (none)",
        sku_name=sku.get("name", ""),
        sku_size=sku.get("size", "") or sku.get("size_display", ""),
        sku_qty_in_base=sku.get("quantity_in_base_unit"),
        sku_price=sku.get("price", 0),
        purchase_qty=anomaly.get("detail", {}).get("quantity", 0),
    )

    def _run(**kwargs):
        return dspy.ChainOfThought(OverseerSignature)(**kwargs)

    pred = run_with_logging(
        prompt_name="overseer",
        prompt_version=OVERSEER_PROMPT_VERSION,
        fn=_run,
        model="gpt-4o",
        prompt=prompt,
    )

    raw = str(getattr(pred, "corrections_json", "") or getattr(pred, "diagnosis", "") or "").strip()
    try:
        for candidate in [raw, re.sub(r"^.*?```(?:json)?\s*", "", raw), re.sub(r"\s*```.*$", "", raw)]:
            candidate = candidate.strip()
            if candidate.startswith("{"):
                parsed = json.loads(candidate)
                return parsed.get("corrections") or []
        parsed = json.loads(raw)
        return parsed.get("corrections") or []
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning("overseer.corrections_parse_failed raw=%s error=%s", raw[:200], e)
        return []
