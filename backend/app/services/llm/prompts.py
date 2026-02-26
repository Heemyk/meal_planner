INGREDIENT_MATCH_PROMPT_VERSION = "v2"
UNIT_NORMALIZE_PROMPT_VERSION = "v4"
SKU_FILTER_PROMPT_VERSION = "v3"
ALLERGEN_INFER_PROMPT_VERSION = "v2"
SKU_SIZE_CONVERT_PROMPT_VERSION = "v3"

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
- base_unit: g | ml | count | tsp | tbsp
- base_unit_qty: numeric base size for 1 unit (e.g., 1.0)
- normalized_qty: numeric amount for this line in base units
- normalized_unit: must equal base_unit

Canonical base units (use these for LP compatibility):
- Weight: always g (flour, sugar, meat, potatoes, butter by weight). Convert lb, oz → g. 1 lb = 453.59 g.
- Volume: always ml (oil, milk, cream, juice). Convert fl oz, cup, tbsp → ml.
- Count: whole items (lemons, eggs, cloves, apples, chicken whole).
- tbsp/tsp: herbs/spices measured by spoon.

Convert to canonical: "4 lb potato" → base_unit=g, normalized_qty=1814.36. "2 cups milk" → base_unit=ml, normalized_qty=473.
If the line is 'to taste' or unspecified, return 0 for normalized_qty.
"""

SKU_FILTER_TEMPLATE = """Given a query and candidate SKU list, select ONLY the items that truly match the query.

STRICT rules — EXCLUDE any candidate that:
1. Is a processed/derived product when the query is the raw ingredient:
   - Query "lemons" → EXCLUDE lemon juice, lemonade, lemon curd, lemon pie filling
   - Query "chicken" → EXCLUDE chicken broth, chicken stock, cooked chicken
   - Query "garlic" → EXCLUDE garlic powder, garlic salt (unless query says powder/salt)
2. Is a beverage when the query is a solid/whole ingredient (e.g. "apples" excludes apple juice)
3. Is a different form: fresh vs dried, whole vs minced/juice, raw vs cooked
4. Is tangentially related (e.g. "lemons" excludes lemon-flavored items, lemon zest alone)

INCLUDE only when:
- The product form matches the query (lemons → whole lemons; lemon juice → bottled/carton juice)
- The ingredient identity is the same (not a substitute or processed variant)

Return selected as a list of candidate objects (subset). If no candidates match strictly, return an empty list []."""

ALLERGEN_INFER_TEMPLATE = """Given a list of ingredients for a recipe, identify which major food allergens are present in THAT recipe ONLY.

Allowed allergen codes only (return ONLY these exact strings, comma-separated):
${allergen_ontology}

CRITICAL: Return ONLY allergens that are actually present in the given ingredients. Do NOT include all allergens. Do NOT include allergens not in the ingredient list. A recipe with just "chicken, rice, salt" should return "none" or empty—not the full ontology.

Rules:
- Only include an allergen if there is direct evidence in the ingredients (e.g. "milk" → milk; "flour" → wheat; "butter" → milk)
- Hidden allergens: flour often contains wheat; mayonnaise contains eggs; compound ingredients may contain multiple
- When uncertain, be conservative: only include when the ingredient could reasonably contain it
- Return empty or "none" if no allergens are present. Most recipes will have 0-3 allergens, not all 10.
"""

DESCRIPTION_TONE_PROMPT_VERSION = "v1"
DISH_DESCRIPTION_PROMPT_VERSION = "v1"

TONE_PROMPT_TEMPLATE = """Given a list of dish names for a dinner party menu, infer the overall tone/vibe.

Return a short tone descriptor (1-2 sentences) for how to describe the dishes. Examples:
- "Elegant and refined, with subtle French-inspired phrasing."
- "Warm Southern comfort, rustic and hearty."
- "Modern fusion: playful, multicultural, inventive."
- "Classic Italian: simple, fresh, family-style."
- "Fine dining: precise, elevated, restrained."

Dish names: {dish_names}

Tone:"""

DISH_DESCRIPTION_TEMPLATE = """Write a short menu-card description for this dish.

TONE: {tone_prompt}

Dish: {dish_name}
Ingredients: {ingredients}
Instructions (first line): {instructions}

First reason about how the dish is composed: Consider each significant ingredient—how it is typically prepared (sautéed, roasted, etc.), how it contributes to texture and flavor, and how the instructions suggest the dish comes together. Then write the description.

Required structure (2-3 sentences):
1. Most significant ingredients (highlight key flavors).
2. How it is composed (cooking method, preparation—based on your reasoning about the ingredients).
3. Origin or how it fits the overall vibe of the menu.

Be concise. Match the tone exactly. No bullet points."""

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

SKU_SIZE_CONVERT_TEMPLATE = """Convert a product size string to a quantity in the target base unit.

IMPORTANT: If size_string is vague ("each", "1 each", empty) but product_name contains quantity (e.g. "Olive Oil, 2 L", "500ml", "67.63 fl oz"), extract and use the quantity from the product name. Prefer name when size lacks usable quantity.

CRITICAL: quantity_in_base_unit MUST be in the target base unit, not the raw size number.
E.g. "5 lb" with base g → quantity_in_base_unit=2267.95 (5 × 453.59), NOT 5.
E.g. "32 fl oz" with base ml → quantity_in_base_unit=946.24 (32 × 29.57), NOT 32.

Rules:
- For weight base (g): convert lb, oz to g. 1 lb = 453.59 g, 1 oz = 28.35 g.
- For volume base (ml): convert fl oz, cup, pint, gallon, L to ml. 1 fl oz = 29.57 ml. 1 L = 1000 ml.
- For count base: "each", "1 count", "1 ct", "per lb" (whole items like chicken) → 1.
- For liquids (oil, cream, milk, juice): use BOTTLE/CARTON volume. "16 fl oz" → 473 ml. Never use count for liquids.
- For "per lb" / "per oz" (sold by weight): use typical pack size. "per lb" chicken → 4 lb pack = 1814 g. size_display = "4 lb".
- size_display: human-friendly. "5 lb" NOT "5 per lb". "each" → "1 each". Liquids → "16 fl oz" or "473 ml".
- product_name: use when size is vague. E.g. "Kirkland Olive Oil, 2 L" + size "each" → 2000 ml for base ml.

Return quantity_in_base_unit (numeric, in target base unit) and size_display (string).
"""
