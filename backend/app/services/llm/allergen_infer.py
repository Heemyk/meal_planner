"""
LLM-based allergen inference for recipes.
Uses the allergen ontology; returns only valid codes. Falls back to keyword matching on failure.
"""

import re
from typing import List

import dspy

from app.services.allergens import ALLERGEN_ONTOLOGY, _infer_allergens_keywords
from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import ALLERGEN_INFER_PROMPT_VERSION, ALLERGEN_INFER_TEMPLATE


class AllergenInferSignature(dspy.Signature):
    """Identify allergens present in a list of ingredients."""

    ingredients: str = dspy.InputField(desc="comma-separated list of ingredient names")
    allergen_ontology: str = dspy.InputField(desc="allowed allergen codes and examples")
    prompt_template: str = dspy.InputField()
    allergens: str = dspy.OutputField(
        desc="comma-separated allergen codes from ontology only, or 'none' if none"
    )


class AllergenInfer(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(AllergenInferSignature)

    def forward(self, ingredients: str, allergen_ontology: str) -> dspy.Prediction:
        ontology_desc = ", ".join(
            f"{k} ({', '.join(v[:4])})" for k, v in ALLERGEN_ONTOLOGY.items()
        )
        template = ALLERGEN_INFER_TEMPLATE.replace("${allergen_ontology}", ontology_desc)
        return self.predict(
            ingredients=ingredients,
            allergen_ontology=allergen_ontology,
            prompt_template=template,
        )


def _parse_allergen_output(raw: str) -> List[str]:
    """Parse LLM output into list of valid allergen codes."""
    if not raw or not isinstance(raw, str):
        return []
    s = raw.strip().lower()
    if s in ("none", "n/a", "nothing", ""):
        return []
    valid = set(ALLERGEN_ONTOLOGY.keys())
    parts = re.split(r"[,;\n]|\band\b", s)
    seen = set()
    for p in parts:
        norm = p.strip().replace(" ", "_")
        if norm in valid and norm not in seen:
            seen.add(norm)
    return sorted(seen)


def infer_allergens_llm(ingredient_names: List[str]) -> List[str]:
    """
    Use LLM to infer allergen codes from ingredient names.
    Returns sorted list of allergen codes from ALLERGEN_ONTOLOGY.
    """
    if not ingredient_names:
        return []
    try:
        infer = AllergenInfer()
        ingredients_str = ", ".join(ingredient_names)
        ontology_str = ", ".join(ALLERGEN_ONTOLOGY.keys())
        prediction = run_with_logging(
            prompt_name="allergen_infer",
            prompt_version=ALLERGEN_INFER_PROMPT_VERSION,
            fn=infer.forward,
            ingredients=ingredients_str,
            allergen_ontology=ontology_str,
        )
        raw = getattr(prediction, "allergens", None) or ""
        return _parse_allergen_output(str(raw))
    except Exception as e:
        from app.logging import get_logger
        get_logger(__name__).warning("allergen_infer.llm_failed error=%s using keywords", e)
        return _infer_allergens_keywords(ingredient_names)
