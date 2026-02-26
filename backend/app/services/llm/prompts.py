INGREDIENT_MATCH_PROMPT_VERSION = "v2"
UNIT_NORMALIZE_PROMPT_VERSION = "v2"
SKU_FILTER_PROMPT_VERSION = "v2"

INGREDIENT_MATCH_TEMPLATE = """You are matching an ingredient line to a canonical ingredient list.
Return a decision with:
- decision: existing | new | similar
- canonical_name: best canonical ingredient name
- rationale: short, non-sensitive explanation
- follow_up_action: if decision=similar, choose one: keep_specific | generalize | substitute
Rules:
1) Use existing if the ingredient is clearly the same (case/format differences only).
2) Use new if it is not in the list and not a close variant.
3) Use similar if it is a close variant or a possible substitution.
4) If similar, follow this reasoning flow internally:
   - Check recipe-criticality (texture, chemistry, cooking method).
   - Check specificity needed for flavor profile.
   - Consider cost/availability tradeoff.
   - Choose follow_up_action accordingly.
Do not include step-by-step reasoning in the rationale.
"""

UNIT_NORMALIZE_TEMPLATE = """Normalize ingredient quantities to a base unit.
Return:
- base_unit: g | ml | count | tsp | tbsp | oz | fl_oz
- base_unit_qty: numeric base size for 1 unit (e.g., 1.0)
- normalized_qty: numeric amount for this line in base units
- normalized_unit: must equal base_unit

Unit selection rules (convert between MEASUREMENT UNITS only, never convert ingredients to other ingredients):
- Weight (flour, sugar, meat, butter by weight): prefer g
- Volume (oil, milk, juice, herbs/spices by spoon): prefer ml
- Whole countable items (lemons, eggs, cloves, apples): prefer count
- tablespoon = tbsp (same unit)

Use the conversion ontology for unit-to-unit conversions only. Do NOT convert ingredient identity (e.g. lemons stay as count, not grams).
If the line is 'to taste' or unspecified, return 0 for normalized_qty.
"""

SKU_FILTER_TEMPLATE = """Given a query and candidate SKU list, select the items that truly match the query.
Prefer matches on ingredient name and avoid unrelated branded drinks or snacks.
Return selected as a list of candidate objects (subset)."""

UNIT_CONVERSION_ONTOLOGY = """Unit-to-unit conversions only (do not convert ingredients to weight/volume):
- 1 tablespoon = 1 tbsp = 3 tsp = 15 ml
- 1 teaspoon = 1 tsp = 5 ml
- 1 cup = 8 fl oz = 240 ml
- 1 fl oz = 29.57 ml
- 1 oz (weight) = 28.35 g
- 1 lb = 16 oz = 453.59 g
- 1 pint = 16 fl oz = 473.18 ml
- 1 quart = 32 fl oz = 946.35 ml
- 1 gallon = 128 fl oz = 3785.41 ml
- 1 stick butter = 8 tbsp = 113 g (when measuring butter by weight/volume)

For whole countable items use count: lemons, eggs, cloves, apples, etc. Do not convert these to grams.
For herbs/spices measured by spoon (e.g. 2 tablespoons rosemary): use tbsp or ml, not grams.
"""
