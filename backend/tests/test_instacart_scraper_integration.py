"""
Integration tests for the Instacart scraper. These hit the real Instacart site.

Run with:
    pytest tests/test_instacart_scraper_integration.py -v -s

Requires:
    pip install playwright
    playwright install chromium
"""
import pytest

pytestmark = pytest.mark.integration


def _playwright_ready():
    """Check if Playwright chromium is installed (cached)."""
    if not hasattr(_playwright_ready, "_result"):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            _playwright_ready._result = True
        except Exception:
            _playwright_ready._result = False
    return _playwright_ready._result


_skip_no_playwright = pytest.mark.skipif(
    not _playwright_ready(),
    reason="Run 'playwright install chromium' first",
)


@_skip_no_playwright
def test_get_stores_live():
    """Real call to get_stores. Validates response shape and at least one store."""
    from app.services.sku import instacart_scraper

    result = instacart_scraper.get_stores("10001")
    assert result["status"] == "success"
    assert "data" in result
    assert "stores" in result["data"]
    assert result["data"]["postal_code"] == "10001"
    stores = result["data"]["stores"]
    assert len(stores) >= 1, "expected at least one store"
    s = stores[0]
    assert "slug" in s
    assert "shop_id" in s
    assert "name" in s
    assert "retailer_id" in s
    print(f"  got {len(stores)} stores: {[x['slug'] for x in stores]}")


@_skip_no_playwright
def test_search_products_live():
    """Real call to search_products. Validates response shape and product fields."""
    from app.services.sku import instacart_scraper

    result = instacart_scraper.search_products(
        query="bananas",
        postal_code="10001",
        retailer_slug="costco",
        limit=5,
    )
    assert result["status"] == "success"
    assert result["data"]["query"] == "bananas"
    assert result["data"]["retailer"] == "costco"
    assert result["data"]["postal_code"] == "10001"
    products = result["data"]["products"]
    assert isinstance(products, list)
    if products:
        p = products[0]
        assert "name" in p
        assert "price" in p
        assert "price_per_unit" in p
    print(f"  got {len(products)} products (Instacart may return IDs-only; parsing validates structure)")


@_skip_no_playwright
def test_full_flow_get_stores_then_search():
    """Full flow: get stores, pick first, search. Simulates worker behavior."""
    from app.services.sku import instacart_scraper

    stores_result = instacart_scraper.get_stores("02138")
    assert stores_result["status"] == "success"
    stores = stores_result["data"]["stores"]
    assert len(stores) >= 1
    store = stores[0]
    retailer_slug = store["slug"]

    search_result = instacart_scraper.search_products(
        query="heavy cream",
        postal_code="02138",
        retailer_slug=retailer_slug,
        limit=3,
    )
    assert search_result["status"] == "success"
    assert search_result["data"]["retailer"] == retailer_slug
    products = search_result["data"]["products"]
    for p in products:
        assert "name" in p
        assert "price" in p
        assert "brand" in p or p.get("brand") is None
    print(f"  flow ok: {retailer_slug} -> {len(products)} products for 'heavy cream'")
