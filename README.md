# Tandem Recipes

Recipe upload and meal-planning app with grocery optimization. Upload recipe text files, get a consolidated shopping list with optimal SKU selection via an ILP solver. Uses LLMs for ingredient matching, unit normalization, and SKU filtering.

## Tech Stack

- **Frontend:** React + Vite, Tailwind CSS
- **Backend:** FastAPI, Celery workers
- **Data:** Postgres, Redis
- **LLM:** DSPy programs (OpenAI) for ingredient matching, unit normalization, SKU filtering

## Quick Start

1. **Copy env and add API key:**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env and set LLM_API_KEY (OpenAI)
   ```

2. **Start services:**
   ```bash
   docker compose up --build
   ```

3. **Open the app:**
   - Frontend: http://localhost:8009
   - Backend API: http://localhost:8008

## Flow

1. Upload recipe text files → parse and normalize ingredients.
2. New ingredients trigger SKU fetch jobs (Instacart).
3. Create a meal plan (target servings, recipes, stores).
4. ILP solver selects recipes and optimal SKU quantities for the shopping list.

## Configuration

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | OpenAI API key (required) |
| `INSTACART_API_KEY` | Parse.bot API key; if empty, uses Playwright scraper |
| `DEFAULT_POSTAL_CODE` | Default zip for store/SKU lookup (default: 10001) |
| `CELERY_WORKER_CONCURRENCY` | SKU fetch workers (default: 6) |

## Reset Data

```bash
./scripts/clean-all.sh
```

Clears recipes, ingredients, SKUs, and plans. Requires `docker compose up` to be running.

## Further Docs

- [docs/architecture.md](docs/architecture.md) — System design
- [docs/runbook.md](docs/runbook.md) — Setup, Instacart/Playwright, troubleshooting
- [docs/api.md](docs/api.md) — API endpoints
