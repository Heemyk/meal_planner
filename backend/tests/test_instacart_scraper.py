"""Tests for the Playwright-based Instacart scraper (instacart_scraper module)."""
import tempfile

from app.services.sku import instacart_scraper


# --- _parse_search_response (indirect via module) ---


def test_parse_search_response_empty():
    """Empty or missing data returns empty list."""
    assert instacart_scraper._parse_search_response({}) == []
    assert instacart_scraper._parse_search_response({"data": {}}) == []
    assert instacart_scraper._parse_search_response(
        {"data": {"searchCrossRetailerGroupResults": {}}}
    ) == []
    assert instacart_scraper._parse_search_response(
        {"data": {"searchCrossRetailerGroupResults": {"groups": []}}}
    ) == []


def test_parse_search_response_with_item_wrapper():
    """GraphQL items as { item: {...} } wrapper."""
    data = {
        "data": {
            "searchCrossRetailerGroupResults": {
                "groups": [
                    {
                        "retailer": {"name": "Costco", "slug": "costco"},
                        "items": [
                            {
                                "item": {
                                    "id": "items_123-456",
                                    "name": "Organic Bananas",
                                    "size": "1 lb",
                                    "brand": {"name": "Chiquita"},
                                    "pricing": {"display": "$2.49", "unitPrice": "$0.25/lb"},
                                    "images": ["https://example.com/banana.jpg"],
                                    "available": True,
                                    "stockStatus": "highlyInStock",
                                }
                            }
                        ],
                    }
                ]
            }
        }
    }
    products = instacart_scraper._parse_search_response(data)
    assert len(products) == 1
    p = products[0]
    assert p["name"] == "Organic Bananas"
    assert p["size"] == "1 lb"
    assert p["brand"] == "Chiquita"
    assert p["price"] == "$2.49"
    assert p["price_per_unit"] == "$0.25/lb"
    assert p["available"] is True
    assert p["stock_status"] == "highlyInStock"
    assert "items_123-456" in str(p["id"])
    assert p["product_id"] == "456" or "456" in p["product_id"]


def test_parse_search_response_direct_item():
    """Items as direct product objects (no node wrapper)."""
    data = {
        "data": {
            "searchCrossRetailerGroupResults": {
                "groups": [
                    {
                        "items": [
                            {
                                "id": "prod-99",
                                "name": "Milk 2%",
                                "price": {"display": "$3.99"},
                            }
                        ],
                    }
                ]
            }
        }
    }
    products = instacart_scraper._parse_search_response(data)
    assert len(products) == 1
    assert products[0]["name"] == "Milk 2%"
    assert products[0]["price"] == "$3.99"


def test_parse_search_response_handles_malformed():
    """Malformed nodes (missing item, wrong types) are skipped gracefully."""
    data = {
        "data": {
            "searchCrossRetailerGroupResults": {
                "groups": [
                    {"items": [None, {}, {"item": None}, {"item": {"name": "Good"}}]}
                ]
            }
        }
    }
    products = instacart_scraper._parse_search_response(data)
    assert len(products) == 1
    assert products[0]["name"] == "Good"


# --- get_stores ---


def test_get_stores_fallback_structure():
    """get_stores returns parse.bot shape with known retailers."""
    result = instacart_scraper.get_stores("10001")
    assert result["status"] == "success"
    assert result["data"]["postal_code"] == "10001"
    assert "stores" in result["data"]
    stores = result["data"]["stores"]
    assert len(stores) >= 3  # costco, walmart, target fallback
    for s in stores:
        assert "slug" in s
        assert "shop_id" in s
        assert "name" in s
        assert "retailer_id" in s


def test_get_stores_returns_fallback_retailers():
    """get_stores returns known fallback retailers (no autosuggest)."""
    result = instacart_scraper.get_stores("02138")
    assert result["status"] == "success"
    assert result["data"]["postal_code"] == "02138"
    stores = result["data"]["stores"]
    assert any(s["slug"] == "costco" for s in stores)
    costco = next(s for s in stores if s["slug"] == "costco")
    assert costco["name"] == "Costco"
    assert costco["shop_id"] == "8621"


# --- search_products ---


def test_search_products_structure(monkeypatch):
    """search_products returns parse.bot shape with products."""
    monkeypatch.setattr(
        instacart_scraper,
        "_ensure_cookies",
        lambda postal_code="": {"cookie": "test"},
    )
    monkeypatch.setattr(
        instacart_scraper,
        "_graphql_request",
        lambda *a, **k: {
            "data": {
                "searchCrossRetailerGroupResults": {
                    "groups": [
                        {
                            "retailer": {"slug": "costco"},
                            "items": [
                                {
                                    "item": {
                                        "id": "x",
                                        "name": "Heavy Cream",
                                        "pricing": {"display": "$4.99"},
                                    }
                                }
                            ],
                        }
                    ]
                }
            }
        },
    )
    result = instacart_scraper.search_products(
        query="heavy cream",
        postal_code="10001",
        retailer_slug="costco",
        limit=5,
    )
    assert result["status"] == "success"
    assert result["data"]["query"] == "heavy cream"
    assert result["data"]["retailer"] == "costco"
    assert result["data"]["postal_code"] == "10001"
    assert len(result["data"]["products"]) == 1
    assert result["data"]["products"][0]["name"] == "Heavy Cream"
    assert result["data"]["products"][0]["price"] == "$4.99"


def test_search_products_respects_limit(monkeypatch):
    """search_products caps products at limit."""
    monkeypatch.setattr(
        instacart_scraper,
        "_ensure_cookies",
        lambda postal_code="": {"cookie": "test"},
    )

    def graphql_many(*a, **k):
        items = [
            {"item": {"id": f"i{i}", "name": f"Product {i}", "pricing": {}}}
            for i in range(10)
        ]
        return {
            "data": {
                "searchCrossRetailerGroupResults": {
                    "groups": [{"retailer": {}, "items": items}]
                }
            }
        }

    monkeypatch.setattr(instacart_scraper, "_graphql_request", graphql_many)
    result = instacart_scraper.search_products(
        query="milk",
        postal_code="10001",
        retailer_slug="costco",
        limit=3,
    )
    assert len(result["data"]["products"]) == 3


def test_search_products_unknown_retailer_uses_fallback(monkeypatch):
    """Unknown retailer slug uses FALLBACK_SHOP_IDS."""
    call_args = []

    def capture_graphql(op, variables, ext, cookies):
        call_args.append(variables)
        return {"data": {"searchCrossRetailerGroupResults": {"groups": []}}}

    monkeypatch.setattr(
        instacart_scraper,
        "_ensure_cookies",
        lambda postal_code="": {"cookie": "test"},
    )
    monkeypatch.setattr(instacart_scraper, "_graphql_request", capture_graphql)
    instacart_scraper.search_products(
        query="eggs",
        postal_code="10001",
        retailer_slug="unknown-retailer-xyz",
        limit=2,
    )
    assert len(call_args) == 1
    assert "shopIds" in call_args[0]
    assert call_args[0]["shopIds"] == instacart_scraper.FALLBACK_SHOP_IDS


# --- get_product_details ---


def test_get_product_details_returns_placeholder(monkeypatch):
    """get_product_details returns minimal placeholder structure."""
    monkeypatch.setattr(
        instacart_scraper,
        "_ensure_cookies",
        lambda postal_code="": {"cookie": "test"},
    )
    monkeypatch.setattr(
        instacart_scraper,
        "_graphql_request",
        lambda *a, **k: {"data": {"items": []}},
    )
    result = instacart_scraper.get_product_details(
        item_id="items_123-456",
        shop_id="8621",
        postal_code="10001",
    )
    assert result["id"] == "items_123-456"
    assert "name" in result
    assert "price" in result
    assert "images" in result


# --- clear_cookie_cache ---


def test_clear_cookie_cache(monkeypatch):
    """clear_cookie_cache removes cache file if it exists."""
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        path = __import__("pathlib").Path(f.name)
    monkeypatch.setenv("INSTACART_COOKIE_CACHE", str(path))
    monkeypatch.setattr(instacart_scraper, "_cookie_path", lambda: path)
    monkeypatch.setattr(instacart_scraper, "_cookie_path_for_postal", lambda pc: path)

    instacart_scraper.clear_cookie_cache()
    assert not path.exists()
