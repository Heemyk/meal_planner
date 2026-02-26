"""
Generate final materials: tone prompt, dish descriptions (with CoT for composition), card metadata.
Triggered post-plan via Generate Final Materials.
"""

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    DESCRIPTION_TONE_PROMPT_VERSION,
    DISH_DESCRIPTION_PROMPT_VERSION,
    TONE_PROMPT_TEMPLATE,
    DISH_DESCRIPTION_TEMPLATE,
)
from app.logging import get_logger

logger = get_logger(__name__)

# Thematic card styles by meal_type (subtle UI variation)
CARD_THEMES = {
    "appetizer": {
        "accent": "amber",
        "font_weight": "medium",
        "border_style": "soft",
    },
    "entree": {
        "accent": "violet",
        "font_weight": "bold",
        "border_style": "emphasized",
    },
    "dessert": {
        "accent": "rose",
        "font_weight": "medium",
        "border_style": "elegant",
    },
    "side": {
        "accent": "emerald",
        "font_weight": "normal",
        "border_style": "minimal",
    },
}


def _generate_tone(dish_names: list[str]) -> str:
    """Generate tone descriptor from dish names."""
    if not dish_names:
        return "Warm and inviting, with classic menu phrasing."
    names_str = ", ".join(dish_names)
    prompt = TONE_PROMPT_TEMPLATE.format(dish_names=names_str)
    try:
        import dspy

        class ToneSignature(dspy.Signature):
            """Infer menu tone from dish names. Output only the tone, 1-2 sentences."""
            prompt: str = dspy.InputField(desc="instructions and dish names")
            tone: str = dspy.OutputField(desc="1-2 sentence tone descriptor")

        predictor = dspy.Predict(ToneSignature)
        pred = run_with_logging(
            prompt_name="description_tone",
            prompt_version=DESCRIPTION_TONE_PROMPT_VERSION,
            fn=lambda **_: predictor(prompt=prompt),
        )
        out = getattr(pred, "tone", "") or ""
        return out.strip() or "Warm and inviting, with classic menu phrasing."
    except Exception as e:
        logger.warning("materials.tone_failed error=%s", e)
        return "Warm and inviting, with classic menu phrasing."


def _generate_dish_description(
    dish_name: str,
    ingredients: list[str],
    instructions: str,
    tone_prompt: str,
) -> str:
    """Generate structured description for one dish."""
    ing_str = ", ".join(ingredients[:20])
    inst = (instructions or "").split(".")[0].strip()
    if inst:
        inst += "."
    prompt = DISH_DESCRIPTION_TEMPLATE.format(
        tone_prompt=tone_prompt,
        dish_name=dish_name,
        ingredients=ing_str,
        instructions=inst,
    )
    try:
        import dspy

        class DishDescriptionSignature(dspy.Signature):
            """Write menu-card description. Output only the description, 1-2 succinct sentences."""
            prompt: str = dspy.InputField(desc="full prompt with tone, dish, ingredients")
            description: str = dspy.OutputField(desc="1-2 sentence succinct menu description")

        predictor = dspy.Predict(DishDescriptionSignature)
        pred = run_with_logging(
            prompt_name="dish_description",
            prompt_version=DISH_DESCRIPTION_PROMPT_VERSION,
            fn=lambda **_: predictor(prompt=prompt),
        )
        out = getattr(pred, "description", "") or ""
        return out.strip() or f"A delicious {dish_name}."
    except Exception as e:
        logger.warning("materials.dish_description_failed dish=%s error=%s", dish_name, e)
        return f"A delicious {dish_name}."


def generate_materials(menu_card: list[dict]) -> list[dict]:
    """
    Generate tone, descriptions, and card metadata for each dish.
    Returns enriched menu_card entries with generated_description, theme, etc.
    """
    if not menu_card:
        return []

    dish_names = [d.get("name", "") for d in menu_card if d.get("name")]
    tone_prompt = _generate_tone(dish_names)

    result = []
    for d in menu_card:
        meal_type = (d.get("meal_type") or "entree").lower()
        theme = CARD_THEMES.get(meal_type) or CARD_THEMES["entree"]
        ingredients = d.get("ingredients") or []
        instructions = d.get("instructions") or d.get("description", "")

        description = _generate_dish_description(
            dish_name=d.get("name", ""),
            ingredients=ingredients,
            instructions=instructions,
            tone_prompt=tone_prompt,
        )

        result.append({
            **d,
            "generated_description": description,
            "theme": theme,
            "meal_type": meal_type,
        })

    return result
