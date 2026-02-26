# System Architecture

## Overview
- **Frontend:** React + Vite for recipe upload and plan generation.
- **Backend:** FastAPI monolith with a Celery worker for SKU fetching.
- **Datastores:** Postgres (relational), Redis (queue + cache).
- **LLM:** DSPy programs for ingredient matching, unit normalization, SKU filtering.

## Core Flow
1. User uploads recipe text files.
2. Backend parses recipes into structured fields.
3. DSPy decides ingredient canonicalization and unit normalization.
4. New ingredients trigger SKU fetch jobs.
5. SKU workers query Instacart API, filter results via DSPy, and store SKUs.
6. User requests a plan; ILP solver picks recipes + SKU quantities.

## Minimal Services
- **Backend API + Worker** share the same codebase to avoid microservice sprawl.
- **Postgres** stores canonical entities and LLM/plan logs.

## Data Flow
- Raw recipes → parsed recipe entities → normalized ingredients.
- Ingredient events → SKU fetch jobs → SKU cache with TTL.
- Plan request → ILP solve → menu plan output.
