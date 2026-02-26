#!/usr/bin/env bash
# Clean all databases: Postgres, Neo4j, Redis.
# Run from project root with: ./scripts/clean-all.sh
# Requires: docker compose up (all services running)

set -e
cd "$(dirname "$0")/.."

echo "Cleaning Postgres..."
docker compose exec postgres psql -U tandem -d tandem -c "
  TRUNCATE TABLE sku, recipeingredient, menuplan, llmcalllog, recipe, ingredient RESTART IDENTITY CASCADE;
"

echo "Cleaning Neo4j..."
docker compose exec neo4j cypher-shell -u neo4j -p password "
  MATCH (n) DETACH DELETE n;
"

echo "Cleaning Redis..."
docker compose exec redis redis-cli FLUSHALL

echo "All databases cleaned."
