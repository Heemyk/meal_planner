#!/usr/bin/env bash
# Clean Postgres: truncate all app tables.
# Run from project root with: ./scripts/clean-postgres.sh
# Requires: docker compose up (postgres running)

set -e
cd "$(dirname "$0")/.."

docker compose exec postgres psql -U tandem -d tandem -c "
  TRUNCATE TABLE sku, recipeingredient, menuplan, llmcalllog, recipe, ingredient RESTART IDENTITY CASCADE;
"
echo "Postgres cleaned."
