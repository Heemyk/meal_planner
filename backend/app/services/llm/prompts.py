INGREDIENT_MATCH_PROMPT_VERSION = "v4"
UNIT_NORMALIZE_PROMPT_VERSION = "v17"
SKU_FILTER_PROMPT_VERSION = "v3"
ALLERGEN_INFER_PROMPT_VERSION = "v2"
SKU_SIZE_EXTRACT_PROMPT_VERSION = "v6"

# Unit normalization: single pass
UNIT_NORMALIZE_TEMPLATE = """Convert recipe ingredient to standard base unit.

FACTORS: {conversion_ontology}

INPUT: {ingredient_text} | canonical: {canonical_name}

base_unit by canonical_name (STRICT — use exactly):
- ANY name containing "oil" (olive oil, vegetable oil, evoo, etc.) → base_unit=ml (NEVER count)
- cream, milk, vinegar, juice, broth, dressing, sauce, maple syrup → base_unit=ml (NEVER count)
- butter, cheese, flour, sugar, rice, croutons, breadcrumbs, nuts, chocolate → base_unit=g (NEVER count)
- potato, russet potato: if "lb"/"kg"/"oz" in ingredient_text → g; else "N potatoes" → count
- rosemary, thyme, oregano, parsley, basil → base_unit=tbsp
- lemon, lime, egg, garlic, chicken, asparagus, salt, pepper, lettuce, bell pepper, onion, tomato, avocado, carrot, celery, apple, banana → base_unit=count
- to taste/pinch/as needed → base_unit=tsp, normalized_qty=0

WEIGHT/VOLUME → COUNT: When ingredient_text gives weight (g, oz, lb) or volume (ml, cup) but canonical is count-type, convert to fractional count. Use WEIGHT PER WHOLE ITEM for solids (60g bell pepper→60/150≈0.4 count). Use juice-per-citrus for citrus juice (75ml lime juice→75/30≈2.5 count; 1 lime≈30ml). NEVER use the recipe number as count (60g≠60 count, 75ml≠75 count).

normalized_unit MUST equal base_unit. Convert using the factors. Output ONLY: base_unit, base_unit_qty=1.0, normalized_qty, normalized_unit
"""

# SKU size conversion: single pass
SKU_SIZE_TEMPLATE = """Convert product size to quantity in base_unit.

FACTORS: {conversion_ontology}

INPUT: size={size_string} product={product_name} base_unit={base_unit}

ml: fl oz×containers (oz w/o lb=fl oz), qt=946ml. g: lb×453.59. count: each=1. When base_unit=g and size="each"/"1 each" for whole produce (bell pepper, onion, tomato, etc.), use WEIGHT PER WHOLE ITEM from factors (e.g. bell pepper→150g). size_display: copy size_string (e.g. "1 lb"), max 20 chars.
Output: quantity_in_base_unit (numeric), size_display (short label)
"""

INGREDIENT_MATCH_TEMPLATE = """You are matching an ingredient line to a canonical ingredient list.
Return a decision with:
- decision: existing | new | similar
- canonical_name: best canonical ingredient name (use SINGULAR form, e.g. tomato not tomatoes)
- rationale: short, non-sensitive explanation
- follow_up_action: if decision=similar, choose one: keep_specific | generalize | substitute

Rules:
1) Use existing if the ingredient is clearly the same. Singular/plural = same: tomato, tomatoes → existing. Cherry tomatoes, roma tomatoes, grape tomatoes → all match "tomato".
2) Consolidate variants: tomato, tomatoes, cherry tomatoes, grape tomatoes, roma → canonical_name: tomato (singular base form).
3) Use new only if truly different (e.g. tomato sauce vs whole tomato).
4) If similar, choose generalize when a specific type can use the general for shopping.
5) For citrus: "lemon juice", "lemon zest", "2 lemons" → canonical_name: lemon (buy whole lemons). Same for lime, orange.
Do not include step-by-step reasoning in the rationale.
"""

UNIT_CONVERSION_ONTOLOGY = """tbsp=15ml, tsp=5ml, cup=240ml, fl oz=29.57ml, oz(wt)=28.35g, lb=453.59g, qt=946ml, quart=946ml, stick butter=113g. 1 lemon≈45ml juice; 1 lime≈30ml juice; 1 clove garlic≈4g; 1 tbsp butter=14g; 1 cup cheese≈100g; 1 cup croutons≈50g. Liquids→ml (never count). Cheese/butter/croutons/flour→g (never count). Lemons/limes/eggs/garlic/asparagus/chicken→count. WEIGHT PER WHOLE ITEM (for count ingredients): bell pepper≈150g, onion≈150g, tomato≈170g, lemon≈120g, lime≈70g, avocado≈170g, potato≈170g, carrot≈60g, celery stalk≈40g, apple≈180g, banana≈120g, egg≈50g, chicken breast≈170g."""

SKU_FILTER_TEMPLATE = """Given a query and candidate SKU list, select ONLY the items that truly match the query.

STRICT rules — EXCLUDE any candidate that:
1. Is a processed/derived product when the query is the raw ingredient
2. Is a beverage when the query is a solid/whole ingredient
3. Is a different form: fresh vs dried, whole vs minced/juice
4. Is tangentially related

Return selected as a list of candidate objects. If no candidates match strictly, return an empty list []."""

ALLERGEN_INFER_TEMPLATE = """Given a list of ingredients for a recipe, identify which major food allergens are present in THAT recipe ONLY.

Allowed allergen codes only (return ONLY these exact strings, comma-separated):
${allergen_ontology}

CRITICAL: Return ONLY allergens actually present. Return empty or "none" if no allergens.
"""

DESCRIPTION_TONE_PROMPT_VERSION = "v1"
DISH_DESCRIPTION_PROMPT_VERSION = "v1"
DISH_COLOR_PROMPT_VERSION = "v1"

TONE_PROMPT_TEMPLATE = """Given a list of dish names for a dinner party menu, infer the overall tone/vibe.
Return a short tone descriptor (1-2 sentences).
Dish names: {dish_names}
Tone:"""

DISH_DESCRIPTION_TEMPLATE = """Write a succinct menu-card description for this dish.
TONE: {tone_prompt}
Dish: {dish_name}
Ingredients: {ingredients}
Instructions (first line): {instructions}
Required: 1–2 short sentences only. Match the tone. No bullet points."""

DISH_COLOR_TEMPLATE = """Pick the background color that best matches the visual vibe or dominant color of this dish.

Dish: {dish_name}
Ingredients: {ingredients}

Choose ONE key from this palette (return only the key, nothing else):
- warm_amber: golden, roasted, lemon, butter, chicken, honey
- cream_tan: mashed potato, risotto, cream sauces, bread
- sage_green: herbs, salad, asparagus, peas, pesto
- tomato_red: tomato, red meat, paprika, beets
- chocolate_brown: chocolate, coffee, gravy, mushroom
- lemon_yellow: citrus, mustard, corn
- forest_green: leafy greens, broccoli, olives
- lavender: berries, eggplant, purple cabbage
- rose: berries, salmon, beet
- soft_gold: caramelized, roasted vegetables"""

# Overseer: post-plan anomaly correction
OVERSEER_PROMPT_VERSION = "v2"
OVERSEER_TEMPLATE = """You are an overseer checking a meal-plan result for unit/conversion errors.

ANOMALY: {reason}
Ingredient: {ingredient_name} (id={ingredient_id})
Current: base_unit={base_unit}, base_unit_qty={base_unit_qty}

RecipeIngredients using this ingredient (include id for corrections):
{recipe_ingredients_blob}

Chosen SKU: {sku_name} | size={sku_size} | quantity_in_base_unit={sku_qty_in_base} | price=${sku_price}
Plan purchased: {purchase_qty} units of this SKU.

Diagnose the error. Common causes: (1) weight/volume given but treated as count (e.g. 75ml lime juice→75 count instead of 2.5); (2) wrong SKU quantity_in_base_unit for "each" produce. You may correct: Ingredient.base_unit, RecipeIngredient.quantity+unit, SKU.quantity_in_base_unit. NEVER change the LP purchase quantity (that would violate the optimization).

Output JSON only:
{{"diagnosis": "brief explanation", "corrections": [{{"type": "ingredient"|"recipe_ingredient"|"sku", "id": <int>, "quantity"?: <float>, "unit"?: "<str>", "base_unit"?: "<str>", "quantity_in_base_unit"?: <float>}}]}}
For recipe_ingredient use "recipe_ingredient_id" to avoid confusion. Omit corrections array if no fix needed."""
