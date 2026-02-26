"""
Generate final materials: tone prompt, dish descriptions (with CoT for composition), card metadata.
Triggered post-plan via Generate Final Materials.
"""

import dspy

from app.services.llm.dspy_client import run_with_logging
from app.services.llm.prompts import (
    DESCRIPTION_TONE_PROMPT_VERSION,
    DISH_COLOR_PROMPT_VERSION,
    DISH_DESCRIPTION_PROMPT_VERSION,
    DISH_COLOR_TEMPLATE,
    TONE_PROMPT_TEMPLATE,
    DISH_DESCRIPTION_TEMPLATE,
)
from app.logging import get_logger

logger = get_logger(__name__)

# Food-vibe palette: background colors that evoke the dish
DISH_COLOR_PALETTE: dict[str, dict[str, str]] = {
    "warm_amber": {"borderColor": "hsl(36 90% 45%)", "accentBg": "hsl(36 90% 55% / 0.08)"},
    "cream_tan": {"borderColor": "hsl(35 40% 55%)", "accentBg": "hsl(35 40% 65% / 0.1)"},
    "sage_green": {"borderColor": "hsl(150 30% 40%)", "accentBg": "hsl(150 30% 50% / 0.08)"},
    "tomato_red": {"borderColor": "hsl(0 70% 50%)", "accentBg": "hsl(0 70% 55% / 0.08)"},
    "chocolate_brown": {"borderColor": "hsl(25 45% 35%)", "accentBg": "hsl(25 40% 50% / 0.1)"},
    "lemon_yellow": {"borderColor": "hsl(48 95% 50%)", "accentBg": "hsl(48 90% 60% / 0.08)"},
    "forest_green": {"borderColor": "hsl(140 50% 35%)", "accentBg": "hsl(140 40% 45% / 0.08)"},
    "lavender": {"borderColor": "hsl(270 50% 55%)", "accentBg": "hsl(270 45% 65% / 0.08)"},
    "rose": {"borderColor": "hsl(340 60% 55%)", "accentBg": "hsl(340 55% 65% / 0.08)"},
    "soft_gold": {"borderColor": "hsl(38 60% 50%)", "accentBg": "hsl(38 55% 60% / 0.08)"},
}

# Thematic card styles by meal_type (fallback when no dish color)
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


def _infer_dish_color(dish_name: str, ingredients: list[str]) -> dict[str, str]:
    """Infer background color that matches the food's vibe. Returns {borderColor, accentBg}."""
    ing_str = ", ".join((ingredients or [])[:15])
    prompt = DISH_COLOR_TEMPLATE.format(dish_name=dish_name or "", ingredients=ing_str)
    try:
        class DishColorSignature(dspy.Signature):
            """Pick the palette key for this dish. Output only the key."""
            prompt: str = dspy.InputField(desc="dish name and ingredients")
            color_key: str = dspy.OutputField(desc="one word key from palette, e.g. warm_amber")

        predictor = dspy.Predict(DishColorSignature)
        pred = run_with_logging(
            prompt_name="dish_color",
            prompt_version=DISH_COLOR_PROMPT_VERSION,
            fn=lambda **_: predictor(prompt=prompt),
        )
        raw = (getattr(pred, "color_key", "") or "").strip().lower()
        key = raw.replace(" ", "_") if raw else ""
        if key in DISH_COLOR_PALETTE:
            return DISH_COLOR_PALETTE[key]
    except Exception as e:
        logger.warning("materials.dish_color_failed dish=%s error=%s", dish_name, e)
    return DISH_COLOR_PALETTE["cream_tan"]


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

        dish_color = _infer_dish_color(dish_name=d.get("name", ""), ingredients=ingredients)

        result.append({
            **d,
            "generated_description": description,
            "theme": theme,
            "meal_type": meal_type,
            "background_color": dish_color.get("accentBg"),
            "border_color": dish_color.get("borderColor"),
        })

    return result
