from app.logging import get_logger
from app.services.graph.neo4j_client import neo4j_client

logger = get_logger(__name__)


def upsert_recipe(recipe_id: int, name: str, servings: int) -> None:
    neo4j_client.run(
        """
        MERGE (r:Recipe {id: $id})
        SET r.name = $name, r.servings = $servings
        """,
        id=recipe_id,
        name=name,
        servings=servings,
    )
    logger.info("neo4j.upsert recipe_id=%s name=%s", recipe_id, name)


def upsert_ingredient(ingredient_id: int, name: str) -> None:
    neo4j_client.run(
        """
        MERGE (i:Ingredient {id: $id})
        SET i.name = $name
        """,
        id=ingredient_id,
        name=name,
    )
    logger.info("neo4j.upsert ingredient_id=%s name=%s", ingredient_id, name)


def link_recipe_ingredient(recipe_id: int, ingredient_id: int, qty: float) -> None:
    neo4j_client.run(
        """
        MATCH (r:Recipe {id: $recipe_id})
        MATCH (i:Ingredient {id: $ingredient_id})
        MERGE (r)-[req:REQUIRES]->(i)
        SET req.qty = $qty
        """,
        recipe_id=recipe_id,
        ingredient_id=ingredient_id,
        qty=qty,
    )


def find_synergistic_recipes(recipe_id: int, min_shared: int = 3) -> list[dict]:
    return neo4j_client.run(
        """
        MATCH (target:Recipe {id: $recipe_id})-[:REQUIRES]->(shared:Ingredient)<-[:REQUIRES]-(other:Recipe)
        WITH other, count(shared) as shared_count
        WHERE shared_count >= $min_shared
        RETURN other.id AS recipe_id, shared_count
        ORDER BY shared_count DESC
        """,
        recipe_id=recipe_id,
        min_shared=min_shared,
    )
