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

## Common Issues
- **LLM errors:** validate `LLM_API_KEY` and model name.
- **Neo4j auth:** verify `NEO4J_AUTH` matches settings.
- **SKU jobs:** ensure Redis is running and worker is up.
