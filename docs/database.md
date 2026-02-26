# Database Schema

## Postgres (source of truth for app data)
- **recipe**: name, servings, instructions, source_file.
- **ingredient**: canonical_name, base_unit, base_unit_qty.
- **recipeingredient**: join table with quantities + units (links recipes to ingredients).
- **sku**: cached Instacart product prices per ingredient (TTL 24h).
- **menuplan**: persisted plan outputs (ILP results).
- **llmcalllog**: prompt/latency audit logs.

Log events: `recipe.created`, `ingredient.created`, `sku.created`, `recipe_ingredients.created`, `db.state`.

## Neo4j (graph for synergy queries)
- Nodes: `Recipe`, `Ingredient`.
- Relationships: `(:Recipe)-[:REQUIRES {qty}]->(:Ingredient)`.

Used for pre-ILP clustering (find recipes that share ingredients). Mirrored from Postgres after each recipe/ingredient upsert.

**Upsert behavior:** We call `MERGE` for every recipe and ingredient we process (both new and existing). MERGE creates if missing, updates if present, so we upsert all touched entities.

Log events: `neo4j.upsert` for recipe and ingredient nodes.

## Redis
- **Celery broker:** Task queue. When you upload recipes, SKU fetch jobs are pushed to Redis; workers pull and process them.
- **Celery result backend:** Task results (if configured) are stored here.
- **Not used for:** Application cache (we use in-memory for unit norm); session storage.

## Cache Strategy
SKUs are cached for 24 hours via `expires_at`. Unit normalizer uses in-memory LRU cache to reduce LLM calls.
