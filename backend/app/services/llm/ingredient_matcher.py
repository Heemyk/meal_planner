import re
from typing import List

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import INGREDIENT_MATCH_PROMPT_VERSION, INGREDIENT_MATCH_TEMPLATE
from app.services.llm.ingredient_retrieval import (
    INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD,
    INGREDIENT_RETRIEVAL_TOP_K,
    retrieve_similar_ingredients,
)


def _parse_bullet_block(text: str) -> dict:
    """Extract decision, canonical_name, rationale from bullet block when LLM returns structured output in one field."""
    out = {}
    for line in (text or "").split("\n"):
        line_lower = line.lower()
        if "canonical_name:" in line_lower:
            idx = line_lower.find("canonical_name:")
            if idx >= 0:
                val = line[idx + len("canonical_name:"):].strip().lstrip(":- ")
                if val:
                    out["canonical_name"] = val
        elif "decision:" in line_lower:
            idx = line_lower.find("decision:")
            if idx >= 0:
                val = line[idx + len("decision:"):].strip().lower()[:20]
                for opt in ("existing", "new", "similar"):
                    if opt in val:
                        out["decision"] = opt
                        break
        elif "rationale:" in line_lower:
            idx = line_lower.find("rationale:")
            if idx >= 0:
                val = line[idx + len("rationale:"):].strip().lstrip(":- ")
                if val:
                    out["rationale"] = val
    return out


def _extract_from_any_field(prediction) -> dict:
    """Try to extract canonical_name, decision, rationale from any string field when LLM misplaces output."""
    fallback = {}
    for attr in ("decision", "rationale", "follow_up_action", "canonical_name"):
        val = getattr(prediction, attr, None)
        if isinstance(val, str) and val.strip():
            parsed = _parse_bullet_block(val)
            if parsed.get("canonical_name") and not fallback.get("canonical_name"):
                fallback["canonical_name"] = parsed["canonical_name"]
            if parsed.get("decision") and not fallback.get("decision"):
                fallback["decision"] = parsed["decision"]
            if parsed.get("rationale") and not fallback.get("rationale"):
                fallback["rationale"] = parsed["rationale"]
    return fallback


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
    # Hybrid: if too many existing ingredients, retrieve top-k by similarity to reduce context
    if len(existing_ingredients) > INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD:
        existing_ingredients = retrieve_similar_ingredients(
            ingredient_text, existing_ingredients, top_k=INGREDIENT_RETRIEVAL_TOP_K
        )
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
    # Extract "existing"|"new"|"similar" if decision contains extra text
    for opt in ("existing", "new", "similar"):
        if opt in decision:
            decision = opt
            break
    rationale = (prediction.rationale or "").strip()
    if not canonical_name or not decision or not rationale:
        fallback = _extract_from_any_field(prediction)
        if not canonical_name and fallback.get("canonical_name"):
            canonical_name = fallback["canonical_name"].strip()
        if not decision and fallback.get("decision"):
            decision = fallback["decision"]
        if not rationale and fallback.get("rationale"):
            rationale = fallback["rationale"].strip()
    if not canonical_name:
        canonical_name = re.sub(r"\d+[\s\/]*(tbsp|tsp|cup|oz|g|ml|clove|lb)[\s\.]*", "", ingredient_text)
        canonical_name = re.sub(r"\s+", " ", canonical_name).strip() or "unknown"
    return {
        "decision": decision[:20] if decision else "new",
        "canonical_name": canonical_name.lower(),
        "rationale": rationale or "",
        "follow_up_action": getattr(prediction, "follow_up_action", ""),
    }
