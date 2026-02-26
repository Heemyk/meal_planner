from typing import Any

import httpx

from app.config import settings
from app.logging import get_logger
from app.services.sku.instacart_scraper import (
    get_product_details as scraper_get_product_details,
    get_stores as scraper_get_stores,
    search_products as scraper_search_products,
)

logger = get_logger(__name__)

INSTACART_TIMEOUT = 30.0


def _use_scraper() -> bool:
    """Use Playwright scraper when parse.bot API key is not set."""
    return not bool(settings.instacart_api_key)


class InstacartClient:
    def __init__(self) -> None:
        self._base_url = settings.instacart_base_url
        self._api_key = settings.instacart_api_key

    def _headers(self) -> dict:
        return {"X-API-Key": self._api_key}

    def get_stores(self, postal_code: str) -> dict:
        logger.info("instacart.get_stores postal_code=%s", postal_code)
        if _use_scraper():
            return scraper_get_stores(postal_code)
        url = f"{self._base_url}/get_stores"
        resp = httpx.get(
            url,
            headers=self._headers(),
            params={"postal_code": postal_code},
            timeout=INSTACART_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def search_products(self, query: str, postal_code: str, retailer_slug: str, limit: int = 5) -> dict:
        logger.info(
            "instacart.search_products query=%s postal=%s retailer=%s limit=%s",
            query,
            postal_code,
            retailer_slug,
            limit,
        )
        if _use_scraper():
            return scraper_search_products(query, postal_code, retailer_slug, limit)
        url = f"{self._base_url}/search_products"
        resp = httpx.get(
            url,
            headers=self._headers(),
            params={
                "query": query,
                "postal_code": postal_code,
                "retailer_slug": retailer_slug,
                "limit": limit,
            },
            timeout=INSTACART_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def get_product_details(self, item_id: str, shop_id: str, postal_code: str) -> dict:
        logger.info("instacart.get_product_details item_id=%s shop_id=%s", item_id, shop_id)
        if _use_scraper():
            return scraper_get_product_details(item_id, shop_id, postal_code)
        url = f"{self._base_url}/get_product_details"
        resp = httpx.get(
            url,
            headers=self._headers(),
            params={
                "item_id": item_id,
                "shop_id": shop_id,
                "postal_code": postal_code,
            },
            timeout=INSTACART_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()


instacart_client = InstacartClient()
