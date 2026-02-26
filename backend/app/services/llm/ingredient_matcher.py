import re
from typing import List

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import INGREDIENT_MATCH_PROMPT_VERSION, INGREDIENT_MATCH_TEMPLATE


def _parse_bullet_block(text: str) -> dict:
    """Extract decision, canonical_name from bullet block when LLM returns structured output in one field."""
    out = {}
    for line in (text or "").split("\n"):
        if "- canonical_name:" in line.lower():
            out["canonical_name"] = line.split(":", 1)[1].strip()
        elif "- decision:" in line.lower():
            out["decision"] = line.split(":", 1)[1].strip().lower()[:20]
    return out


class IngredientMatchSignature(dspy.Signature):
    """Match ingredient with explicit rules and follow-up action."""

    ingredient_text: str = dspy.InputField()
    existing_ingredients: str = dspy.InputField(desc="comma-separated canonical list")
    prompt_template: str = dspy.InputField()
    decision: str = dspy.OutputField(
        desc="one of: existing, new, similar"
    )
    canonical_name: str = dspy.OutputField(desc="best canonical ingredient name")
    rationale: str = dspy.OutputField(desc="short explanation without step-by-step reasoning")
    follow_up_action: str = dspy.OutputField(
        desc="if decision=similar: keep_specific | generalize | substitute; else n/a"
    )


class IngredientMatcher(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(IngredientMatchSignature)

    def forward(self, ingredient_text: str, existing_ingredients: List[str]) -> dspy.Prediction:
        existing_text = ", ".join(existing_ingredients)
        return self.predict(
            ingredient_text=ingredient_text,
            existing_ingredients=existing_text,
            prompt_template=INGREDIENT_MATCH_TEMPLATE,
        )


def match_ingredient(ingredient_text: str, existing_ingredients: List[str]) -> dict:
    matcher = IngredientMatcher()
    prediction = run_with_logging(
        prompt_name="ingredient_match",
        prompt_version=INGREDIENT_MATCH_PROMPT_VERSION,
        fn=matcher.forward,
        ingredient_text=ingredient_text,
        existing_ingredients=existing_ingredients,
    )
    canonical_name = (prediction.canonical_name or "").strip()
    decision = (prediction.decision or "").strip().lower()
    if not canonical_name or not decision:
        fallback = _parse_bullet_block(prediction.decision or "") or _parse_bullet_block(
            getattr(prediction, "rationale", "") or ""
        )
        if not canonical_name and fallback.get("canonical_name"):
            canonical_name = fallback["canonical_name"].strip()
        if not decision and fallback.get("decision"):
            decision = fallback["decision"]
    if not canonical_name:
        canonical_name = re.sub(r"\d+[\s\/]*(tbsp|tsp|cup|oz|g|ml|clove|lb)[\s\.]*", "", ingredient_text)
        canonical_name = re.sub(r"\s+", " ", canonical_name).strip() or "unknown"
    return {
        "decision": decision[:20] if decision else "new",
        "canonical_name": canonical_name.lower(),
        "rationale": prediction.rationale or "",
        "follow_up_action": getattr(prediction, "follow_up_action", ""),
    }
