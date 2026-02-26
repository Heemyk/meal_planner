import respx
from httpx import Response

from app.services.sku.instacart_client import InstacartClient


@respx.mock
def test_instacart_search_products(monkeypatch):
    """Test parse.bot path when API key is set."""
    base_url = "https://example.com"
    monkeypatch.setattr("app.services.sku.instacart_client.settings.instacart_base_url", base_url)
    monkeypatch.setattr("app.services.sku.instacart_client.settings.instacart_api_key", "test-key")
    client = InstacartClient()

    respx.get(f"{base_url}/search_products").mock(
        return_value=Response(
            200,
            json={
                "data": {"products": [{"name": "Milk", "price": "$1.99"}]},
                "status": "success",
            },
        )
    )

    result = client.search_products(query="milk", postal_code="10001", retailer_slug="costco", limit=1)
    assert result["status"] == "success"
    assert result["data"]["products"][0]["name"] == "Milk"


def test_scraper_get_stores_structure(monkeypatch):
    """Scraper get_stores returns parse.bot-style structure. Mock Playwright/cookies."""
    from app.services.sku import instacart_scraper

    monkeypatch.setattr(
        instacart_scraper,
        "_ensure_cookies",
        lambda: {"__Host-instacart_sid": "test", "device_uuid": "test"},
    )
    def fake_graphql(_op, _vars, _ext, _cookies):
        return {"data": {"crossRetailerSearchAutosuggestions": {"retailers": []}}}

    monkeypatch.setattr(instacart_scraper, "_graphql_request", fake_graphql)
    result = instacart_scraper.get_stores("10001")
    assert result["status"] == "success"
    assert "stores" in result["data"]
    assert result["data"]["postal_code"] == "10001"
    # Fallback gives costco, walmart, target
    assert len(result["data"]["stores"]) >= 1
    assert result["data"]["stores"][0]["slug"] == "costco"
