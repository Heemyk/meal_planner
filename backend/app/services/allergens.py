"""
Allergen ontology and meal allergen inference.
Uses the 10 most common food allergens (US FDA / international).
"""

from app.logging import get_logger

logger = get_logger(__name__)

# Top 10 allergens (US + common international)
ALLERGEN_ONTOLOGY = {
    "milk": ["milk", "dairy", "cream", "butter", "cheese", "whey", "casein", "lactose"],
    "eggs": ["egg", "eggs", "mayonnaise", "meringue"],
    "fish": ["fish", "anchovy", "salmon", "tuna", "cod", "tilapia", "sardine", "halibut"],
    "shellfish": [
        "shrimp", "crab", "lobster", "clam", "mussel", "oyster", "scallop",
        "prawn", "crayfish", "shellfish",
    ],
    "tree_nuts": [
        "almond", "walnut", "cashew", "pecan", "pistachio", "macadamia",
        "hazelnut", "brazil nut", "pine nut", "chestnut",
    ],
    "peanuts": ["peanut", "peanuts", "groundnut"],
    "wheat": ["wheat", "flour", "bread", "pasta", "gluten"],
    "soy": ["soy", "soya", "tofu", "tempeh", "edamame", "miso"],
    "sesame": ["sesame", "tahini", "hummus"],
    "mustard": ["mustard"],
}


def infer_allergens_from_ingredients(ingredient_names: list[str]) -> list[str]:
    """
    Given a list of ingredient names, return allergen codes present.
    ingredient_names: canonical ingredient names (lowercase).
    Returns: list of allergen keys from ALLERGEN_ONTOLOGY.
    """
    found = set()
    combined = " ".join(ingredient_names).lower()
    for allergen, keywords in ALLERGEN_ONTOLOGY.items():
        for kw in keywords:
            if kw in combined:
                found.add(allergen)
                break
    return sorted(found)


def get_all_allergen_codes() -> list[str]:
    """Return all allergen codes for UI filtering."""
    return list(ALLERGEN_ONTOLOGY.keys())
