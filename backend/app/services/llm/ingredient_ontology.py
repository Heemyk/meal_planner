"""
Canonical base-unit ontology: maps ingredient types to how they are sold.
Eliminates unit mismatches (e.g. cream in count vs ml) by using a single source of truth.
"""

# Ingredients that are liquids: always ml (sold by volume)
_LIQUIDS = frozenset({
    "oil", "olive oil", "milk", "cream", "heavy cream", "whipped cream", "light cream",
    "juice", "lemon juice", "lime juice", "vinegar", "water", "broth", "stock",
    "honey", "maple syrup", "soy sauce", "wine", "beer",
})

# Ingredients sold by count (whole items, bunches, cloves)
_COUNT = frozenset({
    "lemon", "lime", "orange", "egg", "chicken", "garlic", "asparagus", "broccoli",
    "apple", "banana", "tomato", "onion",
})

# By weight (flour, sugar, butter, potatoes by bag, meat, etc.)
_WEIGHT = frozenset({
    "flour", "sugar", "butter", "potato", "russet potato", "rice", "salt", "pepper",
    "cheese", "meat", "beef", "pork", "chicken breast", "bacon",
})


def get_preferred_base_unit(canonical_name: str, recipe_context: str = "") -> str:
    """
    Return the preferred canonical base unit for an ingredient.
    This is the source of truth for how the ingredient is sold / how LP aggregates.
    """
    c = (canonical_name or "").strip().lower()
    if not c:
        return "count"
    if c in _LIQUIDS:
        return "ml"
    if c in _COUNT:
        return "count"
    if c in _WEIGHT or any(x in c for x in ("flour", "sugar", "butter", "potato", "rice", "salt", "pepper")):
        return "g"
    # Herbs/spices by spoon
    if any(x in c for x in ("rosemary", "thyme", "oregano", "basil", "parsley", "cumin", "paprika")):
        return "tbsp"
    # Default for uncategorized
    return "count"
