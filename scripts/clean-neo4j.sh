#!/usr/bin/env bash
# Clean Neo4j: delete all nodes and relationships.
# Run from project root with: ./scripts/clean-neo4j.sh
# Requires: docker compose up (neo4j running)

set -e
cd "$(dirname "$0")/.."

docker compose exec neo4j cypher-shell -u neo4j -p password "
  MATCH (n) DETACH DELETE n;
"
echo "Neo4j cleaned."
