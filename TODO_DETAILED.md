# Detailed TODO List

## Completed ✓

### 1. Location/Zip from User IP
- **Backend**: `/api/location` endpoint using ip-api.com (geo from client IP)
- **Frontend**: `getLocation()` on mount, stores `postal_code`, `in_us`, `error`
- **Flow**: Pass `postal_code` to upload (FormData) and plan; SKU workers use it for Instacart

### 2. Non-US Handling
- If `country_code != "US"`: return `error` + `postal_code` = default (10001)
- Frontend shows amber banner when `location.error` is set

### 3. LP Customization
- `PlanRequest`: `time_limit_seconds`, `batch_penalty`
- `ILPSolverOptions` + `solve_ilp(..., solver_options=...)`
- Frontend: collapsible "LP options" with time limit and batch penalty inputs

### 4. Meal Types (Appetizer, Entree, Dessert, Side)
- `Recipe.meal_type` column (default `entree`), migration on startup
- `infer_meal_type()` in parser: keyword-based from name + instructions
- `meal_config` in `PlanRequest`: e.g. `{"appetizer": 1, "entree": 1}`
- ILP: meal-type constraints (min batches per type)
- UI: meal config inputs, grayed out when no recipes of that type

### 5. LP Store Filter & Infeasible Handling
- `store_slugs` in `PlanRequest`: filter SKUs by retailer
- Early return with `infeasible_reason` when no SKUs from stores or missing ingredients
- Solver `Infeasible` status → `infeasible_reason` in response
- Frontend: store filter tags, infeasible message display

### 6. Allergens
- `ALLERGEN_ONTOLOGY` (10 allergens) in `app/services/allergens.py`
- `infer_allergens_from_ingredients()` for recipes
- `/api/allergens` endpoint; `exclude_allergens` on recipes + plan
- Frontend: allergen filter toggles, allergens on recipe cards

### 7. Hybrid Ingredient Matching
- `INGREDIENT_MATCH_FULL_CONTEXT_THRESHOLD = 20` (configurable)
- When `len(existing) > 20`: use TF-IDF (sklearn) or sentence-transformers retrieval
- Top-10 similar ingredients passed to LLM instead of full list
- Fallback to first k if retrieval fails

---

## Pending / In Progress

### 8. Card Generation (Post-Plan)
**Scope**: Generate card on "Generate Final Materials" button only.

- [ ] Standard template with subtle thematic variation by meal type
- [ ] Canva-esque expandable preview pane (editable)
- [ ] Export to high-res PDF with print metadata (resolution, bleed, paper stock, size, finishes)
- [ ] Components: `MenuCardEditor`, `CardPreview`, PDF export (e.g. jsPDF or backend render)

### 9. Short Description Generation (Post-Plan)
**Scope**: Same trigger – "Generate Final Materials".

- [ ] Reusable tone prompt from selected meals (fusion / fine dining / southern etc.)
- [ ] Structured description: significant ingredients, composition (CoT), origin/vibe
- [ ] LLM CoT for "how composed" from ingredients
- [ ] Only generate when user clicks – no pre-compute

---

## Implementation Notes

### Config (`backend/app/config.py`)
- `ingredient_match_full_context_threshold`: 20
- `ingredient_retrieval_top_k`: 10

### Dependencies Added
- `scikit-learn>=1.3.0` (TF-IDF fallback)
- Optional: `sentence-transformers` for better embeddings

### Database
- `recipe.meal_type` added via migration in `create_db_and_tables()`
