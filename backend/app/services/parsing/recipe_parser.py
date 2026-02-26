import re
from dataclasses import dataclass
from typing import List

from app.logging import get_logger
from app.storage.models import MEAL_TYPES

logger = get_logger(__name__)


def infer_meal_type(name: str, instructions: str = "") -> str:
    """Infer meal_type from recipe name and instructions. Default: entree."""
    combined = f"{name} {instructions}".lower()
    if any(k in combined for k in ["dessert", "cake", "pie", "cookie", "ice cream", "pudding", "tart", "sorbet"]):
        return "dessert"
    if any(k in combined for k in ["salad", "soup", "dip", "appetizer", "appetiser", "starter", "hors d", "bruschetta"]):
        return "appetizer"
    if any(k in combined for k in ["side", "potato", "asparagus", "vegetable side", "rice side", "bread"]):
        return "side"
    return "entree"


@dataclass
class ParsedRecipe:
    name: str
    servings: int
    ingredients: List[str]
    instructions: str


def _parse_title(line: str) -> tuple[str, int]:
    match = re.match(r"^(.*)\(for\s+(\d+)\s+people\)\s*$", line.strip(), re.IGNORECASE)
    if match:
        return match.group(1).strip(), int(match.group(2))
    return line.strip(), 1


def count_ingredients_in_text(text: str) -> int:
    """
    Count ingredient lines without LLM or full parsing.
    Uses structure only: split on ---, find Ingredients section, count lines starting with -.
    """
    sections = [s.strip() for s in text.split("---") if s.strip()]
    total = 0
    for section in sections:
        lines = [line.rstrip() for line in section.splitlines() if line.strip()]
        mode = None
        for line in lines[1:]:  # skip title
            if line.lower().startswith("ingredients"):
                mode = "ingredients"
                continue
            if line.lower().startswith("instructions"):
                mode = "instructions"
                continue
            if mode == "ingredients" and line.startswith("-"):
                total += 1
    return max(1, total)


def parse_recipe_text(text: str) -> List[ParsedRecipe]:
    sections = [s.strip() for s in text.split("---") if s.strip()]
    recipes: List[ParsedRecipe] = []
    logger.info("parser.start sections=%s", len(sections))
    for section in sections:
        lines = [line.rstrip() for line in section.splitlines() if line.strip()]
        if not lines:
            continue
        name, servings = _parse_title(lines[0])
        ingredients: List[str] = []
        instructions_lines: List[str] = []
        mode = None
        for line in lines[1:]:
            if line.lower().startswith("ingredients"):
                mode = "ingredients"
                continue
            if line.lower().startswith("instructions"):
                mode = "instructions"
                continue
            if mode == "ingredients" and line.startswith("-"):
                ingredients.append(line.lstrip("-").strip())
            elif mode == "instructions":
                instructions_lines.append(line.strip())
        recipes.append(
            ParsedRecipe(
                name=name,
                servings=servings,
                ingredients=ingredients,
                instructions=" ".join(instructions_lines).strip(),
            )
        )
    logger.info("parser.end recipes=%s", len(recipes))
    return recipes
