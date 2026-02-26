INGREDIENT_MATCH_PROMPT_VERSION = "v4"
UNIT_NORMALIZE_PROMPT_VERSION = "v9"
SKU_FILTER_PROMPT_VERSION = "v3"
ALLERGEN_INFER_PROMPT_VERSION = "v2"
SKU_SIZE_CONVERT_PROMPT_VERSION = "v7"
SKU_SIZE_EXTRACT_PROMPT_VERSION = "v3"

# Unit normalization: Pass 1 — reasoning
UNIT_NORMALIZE_REASON_TEMPLATE = """You are converting a recipe ingredient quantity to a standard unit.

CONVERSION FACTORS (use exactly):
{conversion_ontology}

INPUT:
- ingredient_text: {ingredient_text}
- canonical_name: {canonical_name}

EXPLICIT UNIT SELECTION RULES (must follow):
1. "to taste", "pinch", "salt and pepper to taste", "as needed" → base_unit = the unit you infer (tsp/tbsp/count), normalized_qty = 0
2. Liquids: cream, milk, oil, juice, vinegar, broth → base_unit = ml (never count)
3. Butter → base_unit = g (1 tbsp = 14 g)
4. Flour, sugar, potato (by weight), rice → base_unit = g
5. Whole countable: lemons, limes, eggs, garlic (cloves), chicken (whole), asparagus (bunches) → base_unit = count
   - 1 lb asparagus ≈ 1 bunch → count; 2 lbs asparagus → 2 count
   - garlic: cloves or heads as count; 2 lbs garlic ≈ many cloves
6. Herbs/spices by spoon: rosemary, thyme, oregano → base_unit = tbsp
7. Lemon juice with canonical "lemon" → convert tbsp juice to lemon count (1 lemon ≈ 3 tbsp juice)

Think through: What does ingredient_text specify? Which rule applies? Convert using the factors.
Output your reasoning only. No final numbers yet.
"""

# Unit normalization: Pass 2 — produce numbers
UNIT_NORMALIZE_PRODUCE_TEMPLATE = """Produce the normalized quantities.

CONVERSION FACTORS:
{conversion_ontology}

INPUT:
- ingredient_text: {ingredient_text}
- canonical_name: {canonical_name}

REASONING:
{reasoning}

GUARDS:
- If "to taste" / "pinch" / "as needed": normalized_qty = 0
- Liquids (cream, oil, milk) → base_unit must be ml, never count
- Butter → base_unit must be g

Output ONLY: base_unit, base_unit_qty=1.0, normalized_qty, normalized_unit
"""

# SKU size conversion: Pass 1 — reasoning
SKU_SIZE_REASON_TEMPLATE = """Convert product size to quantity in base_unit.

CONVERSION FACTORS:
{conversion_ontology}

INPUT:
- size_string: {size_string}
- product_name: {product_name}
- base_unit: {base_unit}

EXPLICIT RULES:
1. base_unit = ml: Size in fl oz × count of containers. "15 oz, 3-count" = 3 × 15 = 45 fl oz = 1330 ml per pack. "1 qt" = 946 ml.
2. base_unit = g: "5 lb" = 5 × 453.59 g. "2.25 lbs" = 1021 g.
3. base_unit = count: "each" = 1; "4-count" butter = 4 sticks. Asparagus "2.25 lbs" ≈ 2–3 bunches.
4. Liquid products (cream, milk, oil): "oz" without "lb" = fl oz (volume). "1 qt" = 946 ml total.

Output reasoning only. No final numbers yet.
"""

# SKU size conversion: Pass 2 — produce numbers
SKU_SIZE_PRODUCE_TEMPLATE = """Produce the converted size.

CONVERSION FACTORS:
{conversion_ontology}

INPUT: size_string={size_string}, product_name={product_name}, base_unit={base_unit}
REASONING: {reasoning}

GUARDS:
- base_unit=ml and product is cream/milk/oil: quantity_in_base_unit = total ml (fl oz × count × 29.57, or qt→946, L→1000)
- base_unit=g: quantity = total grams
- base_unit=count: quantity = number of purchasable items or estimated count (1 asparagus bunch, 1 lemon, etc.)

Output ONLY: quantity_in_base_unit (numeric), size_display (short label)
"""

SKU_SIZE_EXTRACT_TEMPLATE = """Extract and convert.

Given size_string, product_name, and base_unit:
1. Extract amount and unit from size_string or product_name.
2. Convert to base_unit. For multi-packs (e.g. "15 oz, 3-count"), total = amount × count.
3. Return quantity_in_base_unit (numeric) and size_display (short label). No reasoning.
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

UNIT_CONVERSION_ONTOLOGY = """Use these conversion factors exactly:
- 1 tablespoon = 1 tbsp = 3 tsp = 15 ml
- 1 teaspoon = 1 tsp = 5 ml
- 1 cup = 8 fl oz = 240 ml
- 1 fl oz = 29.57 ml
- 1 oz (weight) = 28.35 g
- 1 lb = 16 oz = 453.59 g
- 1 pint = 16 fl oz = 473.18 ml
- 1 quart = 32 fl oz = 946.35 ml
- 1 gallon = 128 fl oz = 3785.41 ml
- 1 stick butter = 8 tbsp = 113 g
- Lemon juice: 1 lemon ≈ 3 tbsp ≈ 45 ml juice
- Garlic: 1 clove ≈ 4 g; 1 head ≈ 25–30 g
- Butter: 1 tbsp butter = 14 g
For whole countable items use count: lemons, eggs, cloves garlic, apples. Do not convert to grams.
For liquids (cream, milk, oil, juice) use ml.
For herbs/spices by spoon use tbsp or tsp.
"""

UNIT_NORMALIZE_TEMPLATE = """Convert ingredient quantity to target_base_unit.
Output: base_unit, base_unit_qty=1.0, normalized_qty, normalized_unit.
"""

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
