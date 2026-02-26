#!/usr/bin/env bash
# Clean Redis: flush all keys (Celery queue, cache).
# Run from project root with: ./scripts/clean-redis.sh
# Requires: docker compose up (redis running)

set -e
cd "$(dirname "$0")/.."

docker compose exec redis redis-cli FLUSHALL
echo "Redis cleaned."
