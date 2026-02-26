# System Design, Dynamic Imports, and Fallbacks

## 1. System Design Improvements

### Observability & Resilience
- **Structured logging**: Already present; consider adding trace IDs for request correlation (upload → plan → materials).
- **Health checks**: Add `/health` liveness + readiness (Postgres connect, Redis ping). Partial exists in `api/health`.
- **Circuit breaker**: Instacart API and LLM calls have no backoff/circuit breaker. Consider `tenacity` or similar for retries with exponential backoff.
- **Timeouts**: LLM and Instacart have timeouts; ensure Celery task `soft_time_limit` is set for SKU fetch to avoid hung workers.

### Data & Consistency
- **SKU price staleness**: `expires_at` filters expired SKUs but doesn’t trigger refresh. Celery Beat helps; consider proactive refresh N hours before expiry.
- **Idempotency**: Recipe upload isn’t idempotent; re-uploading same file can duplicate recipes. Consider content hash or source_file + name uniqueness.
- **Transaction boundaries**: `_run_processing` in progress does session commits per recipe; a mid-way failure can leave partial data. Consider unit-of-work per file.

### API & Frontend
- **Pagination**: `GET /recipes` and `GET /ingredients-with-skus` return everything. Add pagination or streaming for large catalogs.
- **Rate limiting**: No rate limiting on upload or plan endpoints; heavy usage could overload LLM/Instacart.
- **CORS**: Configured via middleware; ensure production `allow_origins` is restrictive.

### Architecture
- **LLM abstraction**: DSPy is tightly coupled; an `LLMProvider` interface would ease swapping providers.
- **Config validation**: Pydantic settings load at startup; add a `/config/validate` or fail-fast on invalid API keys if critical.
- **Graceful degradation**: When Instacart is down, plan returns "Infeasible". Consider partial plans or cached SKUs only.

---

## 2. Dynamic Imports (Resolved)

All dynamic imports have been moved to module top:

- **progress.py**: `match_ingredient`, `normalize_units`, `settings`, `time`, `Redis`, `celery_app`, `JSONResponse` → top-level
- **optimize.py**: `instacart_client`, `settings`, `get_ingredients_needing_sku_refresh`, `refresh_expired_skus`, `delete_skus_for_ingredients` → top-level
- **tasks.py**: `get_ingredients_needing_sku_refresh` → top-level
- **allergens.py**: `settings`, `infer_allergens_llm` → top-level
- **instacart_client.py**: `instacart_scraper` functions → top-level (aliased)
- **embedding/service.py**: `SentenceTransformer`, `TfidfVectorizer`, `cosine_similarity`, `numpy` → top-level with try/except for optional deps
- **materials_generator.py**: `dspy` → top-level
- **instacart_scraper.py**: `os` → top-level
- **tests**: `__import__("datetime")`, `__import__("pathlib")` → proper imports

Previously:
- `progress.py`: `match_ingredient`, `normalize_units`, `settings`, `time`, `Redis`, `celery_app`, `JSONResponse` inside functions
- `optimize.py`: `instacart_client`, `settings`, `get_ingredients_needing_sku_refresh`, `refresh_expired_skus`, `delete_skus_for_ingredients` inside endpoints
- `tasks.py`: `get_ingredients_needing_sku_refresh` inside task
- `allergens.py`: `settings`, `infer_allergens_llm` inside function
- `instacart_client.py`: `instacart_scraper` (get_stores, search_products, get_product_details) inside methods
- `embedding/service.py`: `SentenceTransformer`, `TfidfVectorizer`, `cosine_similarity`, `numpy` inside `_ensure_loaded` / hot path
- `materials_generator.py`: `dspy` inside try blocks
- `instacart_scraper.py`: `os` inside `_cookie_path`
- Tests: `__import__("datetime")`, `__import__("pathlib")`

---

## 3. Fallbacks (Complete List)

| Location | Fallback | Trigger |
|----------|----------|---------|
| **allergens.py** | `_infer_allergens_keywords` | When `use_llm_allergens=False` or LLM call fails |
| **allergens.py** | `getattr(settings, "use_llm_allergens", True)` | When config key missing |
| **api/location.py** | `default_postal_code` (10001) | Geo API fails, non-US, or no zip |
| **api/location.py** | `getattr(settings, "default_postal_code", DEFAULT_US_POSTAL)` | When config key missing |
| **api/optimize.py** | `(postal_code or "").strip() or settings.default_postal_code` | No postal in list_stores |
| **api/optimize.py** | `s.get("name", s.get("slug", ""))` | Store missing name |
| **api/optimize.py** | `status = result.get("status", "Unknown")` | ILP result missing status |
| **api/progress.py** | `ingredient_totals.get(name, 1)` | File parse fails to count ingredients |
| **api/progress.py** | `f.get("ingredients_unavailable", 0)`, `f.get("ingredient_ids") or []` | Progress structure fields |
| **api/progress.py** | `job_progress_store.get(job_id, {"files": [], "complete": False})` | Job not found |
| **api/progress.py** | `(postal_code or "").strip() or settings.default_postal_code` | No postal in upload |
| **api/recipes.py** | `effective_postal = (postal_code or "").strip() or settings.default_postal_code` | No postal in upload |
| **api/recipes.py** | `base_unit_qty=normalized.get("base_unit_qty", 1.0)` | Normalizer missing field |
| **embedding/service.py** | TFIDF retriever | When `sentence_transformers` not installed |
| **embedding/service.py** | `1e-9` in norm divisor | Avoid division by zero |
| **ilp_solver.py** | `servings_per_recipe.get(rid, 1)` | Missing meal_config entry |
| **ingredient_matcher.py** | `_extract_from_any_field` (fallback dict) | When DSPy output missing canonical_name/decision/rationale |
| **ingredient_matcher.py** | `canonical_name or "unknown"` | Empty match |
| **instacart_client.py** | Playwright scraper | When `instacart_api_key` not set |
| **instacart_scraper.py** | `FALLBACK_SHOP_IDS` (Costco, Walmart, etc.) | When retailer unknown |
| **instacart_scraper.py** | `os.environ.get("INSTACART_COOKIE_CACHE", "./.instacart_cookies.pkl")` | Cookie path default |
| **instacart_scraper.py** | `data.get("ts", 0)` | Cookie cache missing timestamp |
| **instacart_scraper.py** | `data.get("data", {}).get("items") or []` | API response shape |
| **instacart_scraper.py** | `item.get("name", "")`, `vs.get("priceString")`, etc. | Product/price extraction |
| **materials_generator.py** | `"Warm and inviting, with classic menu phrasing."` | Tone generation fails |
| **materials_generator.py** | `f"A delicious {dish_name}."` | Dish description fails |
| **materials_generator.py** | `CARD_THEMES.get(meal_type) or CARD_THEMES["entree"]` | Unknown meal_type |
| **materials_generator.py** | `d.get("instructions") or d.get("description", "")` | Missing instructions |
| **repositories.py** | Top-level `retailer_slug` | Per-SKU retailer_slug missing |
| **repositories.py** | `sku.get("name", "")`, etc. | SKU dict extraction |
| **storage/repositories.py** | `_sanitize_base_unit` → `"count"` | Invalid base_unit |
| **tasks.py** | `postal_code or settings.default_postal_code` | Task called without postal |
| **tasks.py** | `search["data"].get("retailer", retailer_slug)` | Search response missing retailer |
| **tasks.py** | Keyword match on `query in name` | LLM filter returns empty but candidates exist |
| **unit_normalizer.py** | `target_base_unit or "count"` | LLM returns invalid base_unit |
| **sku_size_converter.py** | `base_unit = "count"` | Invalid base_unit passed in |
