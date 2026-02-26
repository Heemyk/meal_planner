# Runbook

## Local Start
1. Copy `backend/.env.example` to `backend/.env` and add API keys.
2. Run `docker compose up --build`.
3. Open `http://localhost:5173` for the frontend.

## Instacart / SKU Fetching
- **Parse.bot (recommended for prices):** Set `INSTACART_API_KEY` in `.env` to use the parse.bot API. Required for reliable prices and brand data.
- **Playwright scraper (free):** If `INSTACART_API_KEY` is empty, the backend uses a Playwright-based scraper that:
  - Launches headless Chromium to obtain session cookies from instacart.com
  - Calls Instacart's GraphQL API (SearchCrossRetailerGroupResults, etc.)
  - Caches cookies in `./.instacart_cookies.pkl` for ~30 min to reduce browser launches
- **Local dev:** Run `playwright install chromium` in the backend venv for the scraper.
- **Docker:** The Dockerfile installs Chromium via `playwright install --with-deps chromium`.
- **No prices/brand in scraper:** Instacart often requires an authenticated session (logged-in user with address) to return prices. The Playwright scraper uses anonymous cookies; if you see `Items batch first item price=None`, use parse.bot or clear cookies: `rm .instacart_cookies_*.pkl`.

## SKU / Price TTL & Refresh
- **TTL**: `SKU_CACHE_TTL_HOURS` (default 24) — SKU prices expire after this many hours. Expired rows stay in DB but are filtered out (`expires_at > now`).
- **Data separation**: Recipes, Ingredients, RecipeIngredient are persistent (parsed from uploads). SKU is price data with TTL. You can reset/re-run SKU extraction without touching parsed data.
- **Manual refresh**: `POST /api/sku/refresh` with body `{ "ingredient_ids": [1,2], "postal_code": "10001" }` — both optional. Enqueues fetch jobs for ingredients with no valid prices.
- **Reset & re-fetch**: `POST /api/sku/reset` with body `{ "ingredient_ids": [1,2], "postal_code": "10001" }` — deletes all SKUs for those ingredients, then enqueues refresh. Use to force full re-fetch.
- **Automatic refresh**: Celery Beat runs every 30 min, finds ingredients with no valid SKUs, and enqueues fetch_skus_for_ingredient. Requires `beat` service (see docker-compose).

# Parallelization & Utilization
- **Ingredient parsing:** `INGREDIENT_BATCH_MAX_WORKERS` (default 8) – threads per recipe for LLM match+normalize.
- **SKU fetching:** `CELERY_WORKER_CONCURRENCY` (default 10) – Celery workers for `fetch_skus_for_ingredient`.
- **Utilization endpoint:** `GET /api/utilization` – shows configured limits, active SKU tasks, queue length, tuning hints.
- **Timing logs:** Grep `[TIMING]` in backend logs for actual runtimes (ingredient.batch.parallel, sku.fetch.total).
- **Batching:** Ingredient LLM calls are parallelized but not batched (each is a separate request). Instacart has no batch search API; SKU tasks run one-per-ingredient.

## Optimizing workers
- **Ingredient workers:** If `ingredient.batch.parallel` latency is high, increase `INGREDIENT_BATCH_MAX_WORKERS`. Use 2–4× CPU cores for I/O-bound LLM. Don’t exceed ~16 (rate limits).
- **SKU workers:** If `sku_queue_length` stays high and `active_tasks` is below concurrency, increase `CELERY_WORKER_CONCURRENCY`. Start at 10–20. Restart worker after changing.

## Common Issues
- **LLM errors:** validate `LLM_API_KEY` and model name.
- **Neo4j auth:** verify `NEO4J_AUTH` matches settings.
- **SKU jobs:** ensure Redis is running and worker is up.
