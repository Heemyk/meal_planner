from pathlib import Path

from app.storage.models import Ingredient, Recipe, RecipeIngredient, SKU


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_allergens_endpoint(client):
    response = client.get("/api/allergens")
    assert response.status_code == 200
    data = response.json()
    assert "allergens" in data
    assert isinstance(data["allergens"], list)
    assert "milk" in data["allergens"]
    assert len(data["allergens"]) == 10


def test_recipes_list_exclude_allergens(client, session):
    r1 = Recipe(name="A", servings=2, instructions="Cook", source_file="x", allergens=["milk"])
    r2 = Recipe(name="B", servings=2, instructions="Cook", source_file="x", allergens=["wheat"])
    session.add(r1)
    session.add(r2)
    session.commit()
    response = client.get("/api/recipes?exclude_allergens=milk")
    assert response.status_code == 200
    recipes = response.json()
    assert len(recipes) == 1
    assert recipes[0]["name"] == "B"
    assert recipes[0]["allergens"] == ["wheat"]


def test_recipes_list_returns_allergens(client, session):
    r = Recipe(name="Milk Dish", servings=2, instructions="Cook", source_file="x", allergens=["milk"])
    session.add(r)
    session.commit()
    response = client.get("/api/recipes")
    assert response.status_code == 200
    recipes = response.json()
    assert len(recipes) == 1
    assert recipes[0]["allergens"] == ["milk"]


def test_recipe_upload(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.recipes.match_ingredient",
        lambda ingredient_text, existing: {
            "decision": "new",
            "canonical_name": ingredient_text.split()[0],
            "rationale": "test",
        },
    )
    monkeypatch.setattr(
        "app.api.recipes.normalize_units",
        lambda ingredient_text: {
            "base_unit": "count",
            "base_unit_qty": 1.0,
            "normalized_qty": 1.0,
            "normalized_unit": "count",
        },
    )
    monkeypatch.setattr(
        "app.api.recipes.fetch_skus_for_ingredient",
        type("DummyTask", (), {"delay": staticmethod(lambda *_args, **_kwargs: None)}),
    )
    monkeypatch.setattr("app.api.recipes.upsert_recipe", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.api.recipes.upsert_ingredient", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.api.recipes.link_recipe_ingredient", lambda *args, **kwargs: None)

    repo_root = Path(__file__).resolve().parents[2]
    file_path = repo_root / "intern-dataset-main" / "1.txt"
    with file_path.open("rb") as handle:
        response = client.post("/api/recipes/upload", files={"files": ("1.txt", handle, "text/plain")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["recipes_created"] == 3
    assert payload["ingredients_created"] > 0


def test_plan_endpoint(client, session):
    recipe = Recipe(name="Test", servings=2, instructions="Cook", source_file="unit")
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    ingredient = Ingredient(name="milk", canonical_name="milk", base_unit="ml", base_unit_qty=1.0)
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)

    recipe_ing = RecipeIngredient(
        recipe_id=recipe.id,
        ingredient_id=ingredient.id,
        quantity=100,
        unit="ml",
        original_text="100 ml milk",
    )
    session.add(recipe_ing)
    session.commit()

    sku = SKU(
        ingredient_id=ingredient.id,
        name="Milk 1L",
        size="1000 ml",
        price=2.0,
        price_per_unit="$0.002/ml",
        retailer_slug="test",
        postal_code="10001",
        expires_at=__import__("datetime").datetime.utcnow()
        + __import__("datetime").timedelta(hours=1),
    )
    session.add(sku)
    session.commit()

    response = client.post("/api/plan", json={"target_servings": 2})
    assert response.status_code == 200
    payload = response.json()
    assert "plan_payload" in payload
    assert "status" in payload


def test_plan_with_custom_options(client, session):
    recipe = Recipe(name="Test", servings=2, instructions="Cook", source_file="unit")
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    ing = Ingredient(name="milk", canonical_name="milk", base_unit="ml", base_unit_qty=1.0)
    session.add(ing)
    session.commit()
    session.refresh(ing)
    session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=ing.id, quantity=100, unit="ml", original_text="100 ml milk"))
    session.add(SKU(ingredient_id=ing.id, name="Milk", size="1000 ml", price=2.0, retailer_slug="test", postal_code="10001", expires_at=__import__("datetime").datetime.utcnow() + __import__("datetime").timedelta(hours=1)))
    session.commit()
    response = client.post(
        "/api/plan",
        json={"target_servings": 2, "time_limit_seconds": 5, "batch_penalty": 0.0001},
    )
    assert response.status_code == 200
    assert response.json().get("status") in ("Optimal", "Not Solved")
