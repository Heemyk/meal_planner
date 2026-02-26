"""
Playwright-based Instacart GraphQL scraper. Replaces parse.bot when API key is not set.
Uses real browser sessions to obtain cookies and call Instacart's GraphQL API.
"""
from __future__ import annotations

import asyncio
import json
import os
import pickle
import time
import uuid
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import async_playwright
from redis import Redis
from redis.lock import Lock

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

# Apollo persisted query hashes (from network traffic analysis)
SEARCH_HASH = "fd9da7d59604d397e561e1c36afaa4c23c27179ea613d9fb8aded558bafb804e"
# Items batch lookup: resolves itemIds to full product data (name, price, image, etc.)
ITEMS_HASH = "5116339819ff07f207fd38f949a8a7f58e52cc62223b535405b087e3076ebf2f"
# CrossRetailerSearchAutosuggestions: returns retailerId->retailerSlug for retailer-type suggestions
AUTOSUGGEST_HASH = "89ec32ea85c9b7ea89f7b4a071a5dd4ec1335831ff67035a0f92376725c306a3"

# Retailer slug -> retailer_id mapping (Costco=5, Walmart=13, etc.)
RETAILER_IDS: dict[str, str] = {
    "costco": "5",
    "walmart": "13",
    "target": "90",
    "whole-foods": "12",
    "wegmans": "119",
    "aldi": "26",
    "kroger": "375",
    "safeway": "118",
    "cvs": "144",
    "walgreens": "163",
    "key-food": "39",
}

# Default zone ID (392 = Northeast US). May need adjustment per postal code.
DEFAULT_ZONE_ID = "392"

# Known shop IDs per retailer slug (from captured traffic). Used for search_products.
RETAILER_SHOP_IDS: dict[str, list[str]] = {
    "costco": ["8621"],
    "walmart": ["557"],
    "target": ["4893"],
    "whole-foods": ["63766"],
    "wegmans": ["943"],
    "aldi": ["3949"],
    "kroger": ["602909", "602931"],
    "safeway": ["1831"],
    "cvs": ["4342"],
    "walgreens": ["3393"],
    "key-food": ["596274"],
}

# Fallback when retailer unknown. Order matches typical search relevance (Costco first, etc.)
FALLBACK_SHOP_IDS = ["8621", "557", "4893", "596274", "63766", "943", "3949", "602909"]

def _cookie_path() -> Path:
    return Path(os.environ.get("INSTACART_COOKIE_CACHE", "./.instacart_cookies.pkl"))


COOKIE_MAX_AGE_SEC = 30 * 60  # 30 minutes


def _cookie_path_for_postal(postal_code: str) -> Path:
    base = _cookie_path()
    if postal_code:
        return base.parent / f".instacart_cookies_{postal_code}.pkl"
    return base


def _load_cookies(postal_code: str = "") -> dict[str, str] | None:
    try:
        p = _cookie_path_for_postal(postal_code)
        if p.exists():
            with open(p, "rb") as f:
                data = pickle.load(f)
            if time.time() - data.get("ts", 0) < COOKIE_MAX_AGE_SEC:
                return data.get("cookies")
    except Exception as e:
        logger.warning("instacart_scraper: failed to load cookies: %s", e)
    return None


def _save_cookies(cookies: dict[str, str], postal_code: str = "") -> None:
    try:
        with open(_cookie_path_for_postal(postal_code), "wb") as f:
            pickle.dump({"ts": time.time(), "cookies": cookies}, f)
    except Exception as e:
        logger.warning("instacart_scraper: failed to save cookies: %s", e)


async def _get_fresh_cookies(postal_code: str) -> dict[str, str]:
    """Navigate to store with postal code to establish delivery zone (required for prices).
    HAR showed prices when session was on search page (/store/s?k=...). We:
    1) Load /store?address=X to set address
    2) Load /store/s?k=bananas to trigger Search with zone/context (establishes pricing)
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()
        store_url = f"https://www.instacart.com/store?address={postal_code}"
        logger.info("instacart_scraper: navigating to store (postal=%s)", postal_code)
        await page.goto(store_url, wait_until="load", timeout=30000)
        await page.wait_for_timeout(4000)
        # Load search page to establish zone/pricing context (HAR: /store/s?k=X had prices)
        search_warmup = "https://www.instacart.com/store/s?k=bananas"
        await page.goto(search_warmup, wait_until="load", timeout=20000)
        await page.wait_for_timeout(6000)
        cookies_list = await context.cookies()
        await browser.close()
        cookies = {c["name"]: c["value"] for c in cookies_list}
        return cookies


def _ensure_cookies(postal_code: str = "10001") -> dict[str, str]:
    cached = _load_cookies(postal_code)
    if cached:
        return cached
    # Only one worker may fetch cookies at a time to avoid 6 parallel Playwright sessions
    # overwhelming Instacart and timing out.
    redis_client = Redis.from_url(settings.redis_url)
    lock = Lock(
        redis_client,
        f"instacart:cookie_fetch:{postal_code or 'default'}",
        timeout=90,
    )
    acquired = lock.acquire(blocking=True, blocking_timeout=120)
    try:
        if not acquired:
            cached = _load_cookies(postal_code)
            if cached:
                return cached
            raise RuntimeError("Could not acquire cookie fetch lock; retry task.")
        cached = _load_cookies(postal_code)
        if cached:
            return cached
        cookies = asyncio.run(_get_fresh_cookies(postal_code))
        _save_cookies(cookies, postal_code)
        return cookies
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass


def _graphql_request(
    operation_name: str,
    variables: dict[str, Any],
    extensions: dict[str, Any],
    cookies: dict[str, str],
) -> dict[str, Any]:
    params = {
        "operationName": operation_name,
        "variables": json.dumps(variables, separators=(",", ":")),
        "extensions": json.dumps(extensions, separators=(",", ":")),
    }
    qs = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    url = f"https://www.instacart.com/graphql?{qs}"
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instacart.com/store",
        "Cookie": cookie_str,
        "x-client-identifier": "web",
        "x-ic-view-layer": "true",
        "x-page-view-id": str(uuid.uuid4()),
        "cache-control": "no-cache",
        "pragma": "no-cache",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 403:
            raise RuntimeError("Instacart returned 403 — cookies expired, cache cleared")
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            logger.warning("instacart_scraper: GraphQL errors: %s", data["errors"])
        return data


def _fetch_items_batch(
    item_ids: list[str],
    shop_id: str,
    postal_code: str,
    zone_id: str = DEFAULT_ZONE_ID,
) -> list[dict[str, Any]]:
    """Fetch full product data for item IDs via Items GraphQL operation."""
    if not item_ids:
        return []
    cookies = _ensure_cookies(postal_code)
    variables = {
        "ids": item_ids,
        "shopId": shop_id,
        "zoneId": zone_id,
        "postalCode": postal_code,
    }
    ext = {"persistedQuery": {"version": 1, "sha256Hash": ITEMS_HASH}}
    data = _graphql_request("Items", variables, ext, cookies)
    items_raw = data.get("data", {}).get("items") or []
    products = _parse_items_response(data)
    if items_raw:
        it = items_raw[0]
        p = it.get("price") or {}
        vs = (p.get("viewSection") or {}) if isinstance(p, dict) else {}
        price_val = vs.get("priceString") if isinstance(vs, dict) else None
        brand_val = it.get("brandName")
        logger.info(
            "instacart_scraper: Items batch first item price=%s brandName=%s (shop=%s zone=%s postal=%s)",
            price_val,
            brand_val,
            shop_id,
            zone_id,
            postal_code,
        )
        if not price_val and products:
            logger.warning(
                "instacart_scraper: Items returned no price (zone/session issue). Try: rm .instacart_cookies_*.pkl"
            )
    return products


def _fetch_retailer_slugs_from_autosuggest(
    cookies: dict[str, str],
    retailer_ids: list[str],
    postal_code: str = "",
    zone_id: str = DEFAULT_ZONE_ID,
) -> dict[str, str]:
    """Call CrossRetailerSearchAutosuggestions to get retailerId->retailerSlug.
    Autosuggest returns retailer suggestions when query matches retailer names.
    All slugs come from the API; no preset fallback.
    """
    if not retailer_ids:
        return {}
    rid_to_slug: dict[str, str] = {}
    needed = set(str(r) for r in retailer_ids)
    # Single-letter queries that commonly match retailer names
    for q in ("a", "c", "k", "s", "t", "w", "r", "b", "p", "m"):
        if not needed:
            break
        variables: dict[str, Any] = {
            "query": q,
            "limit": 20,
            "retailerIds": list(needed)[:50],  # API may limit
            "zoneId": zone_id,
        }
        if postal_code:
            variables["postalCode"] = postal_code
        ext = {"persistedQuery": {"version": 1, "sha256Hash": AUTOSUGGEST_HASH}}
        try:
            data = _graphql_request("CrossRetailerSearchAutosuggestions", variables, ext, cookies)
        except Exception as e:
            logger.debug("instacart_scraper: Autosuggest query=%s failed: %s", q, e)
            continue
        sugg = data.get("data", {}).get("crossRetailerSearchAutosuggestions", [])
        for s in sugg:
            rid = s.get("retailerId")
            rslug = s.get("retailerSlug")
            rid_str = str(rid) if rid is not None else ""
            if rid_str and rslug and rid_str in needed:
                rid_to_slug[rid_str] = rslug
                needed.discard(rid_str)
    if needed:
        logger.debug("instacart_scraper: Autosuggest missed retailerIds=%s", list(needed))
    return rid_to_slug


def _extract_price_from_item(item: dict[str, Any]) -> tuple[str, str]:
    """Extract display price and price-per-unit from item's price/pricing object.
    Supports both legacy (display, price, unitPrice) and viewSection (priceString, pricePerUnitString) formats.
    """
    price_info = item.get("pricing", {}) or item.get("price", {}) or {}
    if not isinstance(price_info, dict):
        return str(price_info), ""
    # Legacy format
    display = price_info.get("display") or price_info.get("price") or ""
    unit = price_info.get("unitPrice") or ""
    # viewSection format (used by Search and Items when authenticated)
    vs = price_info.get("viewSection") or {}
    if isinstance(vs, dict):
        if not display:
            display = vs.get("priceString") or vs.get("priceValueString") or vs.get("fullPriceString") or ""
        if not display and vs.get("itemCard"):
            display = (vs["itemCard"] or {}).get("priceString") or ""
        if not unit:
            unit = vs.get("pricePerUnitString") or (vs.get("itemCard") or {}).get("pricePerUnitString") or ""
    return display or "", unit or ""


def _parse_items_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract products from Items GraphQL response (parse.bot-style)."""
    products: list[dict[str, Any]] = []
    try:
        items = data.get("data", {}).get("items") or []
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = item.get("id") or item.get("productId") or ""
            display, unit = _extract_price_from_item(item)
            view = item.get("viewSection") or {}
            img = view.get("itemImage") or {}
            img_url = img.get("url") if isinstance(img, dict) else ""
            if isinstance(img_url, dict):
                img_url = img_url.get("url", "") or ""
            avail = item.get("availability") or {}
            available = avail.get("available", True) if isinstance(avail, dict) else True
            brand = item.get("brandName")
            if not brand and isinstance(item.get("brand"), dict):
                brand = (item.get("brand") or {}).get("name")
            products.append({
                "id": pid,
                "name": item.get("name", ""),
                "size": item.get("size"),
                "brand": brand,
                "price": display,
                "rating": item.get("productRating"),
                "available": available,
                "image_url": img_url or "",
                "categories": None,
                "product_id": str(item.get("productId", "")),
                "is_sponsored": False,
                "rating_count": None,
                "stock_status": (avail.get("stockLevel") if isinstance(avail, dict) else None) or "unknown",
                "price_per_unit": unit or "",
            })
    except Exception as e:
        logger.warning("instacart_scraper: parse_items_response error: %s", e)
    return products


def _parse_search_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract products from SearchCrossRetailerGroupResults response."""
    products: list[dict[str, Any]] = []
    try:
        root = data.get("data", {}).get("searchCrossRetailerGroupResults", {})
        if not root:
            return products
        # Instacart can return: groups[].items (legacy) or results[].items
        groups = root.get("groups") or root.get("retailerProductGroups") or []
        results = root.get("results") or []
        for group in groups:
            retailer = group.get("retailer") or {}
            items = group.get("items") or []
            retailer_id = str(retailer.get("id", "") or group.get("retailerId", "")) if (retailer.get("id") or group.get("retailerId")) else ""
            shop_id = str(retailer.get("shopId", "") or group.get("shopId", "")) if (retailer.get("shopId") or group.get("shopId")) else ""
            for node in items:
                if isinstance(node, dict) and "item" in node:
                    item = node.get("item")
                else:
                    item = node if isinstance(node, dict) else None
                if not item or not isinstance(item, dict):
                    continue
                display, unit = _extract_price_from_item(item)
                pid = item.get("id") or item.get("productId") or item.get("itemId") or ""
                if isinstance(pid, dict):
                    pid = pid.get("value", str(pid))
                images = item.get("images") or []
                img_url = ""
                if images:
                    first = images[0] if isinstance(images[0], str) else (images[0].get("url") if isinstance(images[0], dict) else "")
                    img_url = first or ""
                brand = (
                    (item.get("brand") or {}).get("name")
                    if isinstance(item.get("brand"), dict)
                    else item.get("brandName") or item.get("brand")
                )
                products.append({
                    "id": pid,
                    "name": item.get("name", ""),
                    "size": item.get("size"),
                    "brand": brand,
                    "price": display,
                    "rating": item.get("rating"),
                    "available": item.get("available", True),
                    "image_url": img_url,
                    "categories": item.get("categories"),
                    "product_id": str(pid).split("-")[-1] if pid else "",
                    "is_sponsored": item.get("isSponsored", False),
                    "rating_count": item.get("ratingCount") or item.get("reviewCount"),
                    "stock_status": item.get("stockStatus", "unknown"),
                    "price_per_unit": unit or "",
                    "retailer_id": retailer_id,
                    "shop_id": shop_id,
                })
        for result in results:
            items = result.get("items") or result.get("featuredProducts") or []
            retailer_id = str(result.get("retailerId", "")) if result.get("retailerId") else ""
            shop_id = str(result.get("shopId", "")) if result.get("shopId") else ""
            for node in items:
                if isinstance(node, dict) and "item" in node:
                    item = node.get("item")
                else:
                    item = node if isinstance(node, dict) else None
                if not item or not isinstance(item, dict):
                    continue
                display, unit = _extract_price_from_item(item)
                pid = item.get("id") or item.get("productId") or item.get("itemId") or ""
                if isinstance(pid, dict):
                    pid = pid.get("value", str(pid))
                images = item.get("images") or []
                img_url = images[0] if images and isinstance(images[0], str) else (images[0].get("url", "") if images and isinstance(images[0], dict) else "")
                brand = (
                    (item.get("brand") or {}).get("name")
                    if isinstance(item.get("brand"), dict)
                    else item.get("brandName") or item.get("brand")
                )
                products.append({
                    "id": pid,
                    "name": item.get("name", ""),
                    "size": item.get("size"),
                    "brand": brand,
                    "price": display,
                    "rating": item.get("rating"),
                    "available": item.get("available", True),
                    "image_url": img_url or "",
                    "categories": item.get("categories"),
                    "product_id": str(pid).split("-")[-1] if pid else "",
                    "is_sponsored": item.get("isSponsored", False),
                    "rating_count": item.get("ratingCount") or item.get("reviewCount"),
                    "stock_status": item.get("stockStatus", "unknown"),
                    "price_per_unit": unit or "",
                    "retailer_id": retailer_id,
                    "shop_id": shop_id,
                })
    except Exception as e:
        logger.warning("instacart_scraper: parse_search_response error: %s", e)
    return products


def get_stores(postal_code: str) -> dict[str, Any]:
    """
    Return stores for a postal code in parse.bot format.
    Uses known retailer mapping (no autosuggest).
    """
    slug_to_info = {
            "costco": {
                "name": "Costco",
                "slug": "costco",
                "type": "Club/Warehouse Store",
                "pickup": False,
                "shop_id": "8621",
                "delivery": True,
                "logo_url": "",
                "categories": ["Groceries", "Wholesale"],
                "retailer_id": "5",
                "retailer_location_id": "284",
            },
            "walmart": {
                "name": "Walmart",
                "slug": "walmart",
                "type": "Grocery",
                "pickup": True,
                "shop_id": "557",
                "delivery": True,
                "logo_url": "",
                "categories": ["Groceries"],
                "retailer_id": "13",
                "retailer_location_id": "",
            },
            "target": {
                "name": "Target",
                "slug": "target",
                "type": "Grocery",
                "pickup": True,
                "shop_id": "4893",
                "delivery": True,
                "logo_url": "",
                "categories": ["Groceries"],
                "retailer_id": "90",
                "retailer_location_id": "",
            },
        }

    stores = list(slug_to_info.values())
    return {"data": {"stores": stores, "postal_code": postal_code}, "status": "success"}


def search_products(
    query: str,
    postal_code: str,
    retailer_slug: str,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Search products using SearchCrossRetailerGroupResults.
    Uses cross-retailer search (broad shopIds) to get signpostRetailerShopIds ranking,
    then picks the best store for the query. Search response items may include prices;
    when only itemIds are returned, resolves via Items batch.
    """
    cookies = _ensure_cookies(postal_code)
    slug = (retailer_slug or "").lower().replace(" ", "-")
    # Use broad shopIds for cross-retailer search (needed for signpostRetailerShopIds)
    shop_ids = FALLBACK_SHOP_IDS

    variables = {
        "overrideFeatureStates": [],
        "searchSource": "cross_retailer_search",
        "query": query,
        "pageViewId": str(uuid.uuid4()),
        "shopIds": shop_ids,
        "disableAutocorrect": False,
        "includeDebugInfo": False,
        "autosuggestImpressionId": None,
        "first": limit,
        "shopId": "0",
        "zoneId": DEFAULT_ZONE_ID,
        "postalCode": postal_code,
    }
    ext = {"persistedQuery": {"version": 1, "sha256Hash": SEARCH_HASH}}
    try:
        data = _graphql_request("SearchCrossRetailerGroupResults", variables, ext, cookies)
    except RuntimeError as e:
        if "403" in str(e):
            clear_cookie_cache(postal_code)
            cookies = _ensure_cookies(postal_code)
            data = _graphql_request("SearchCrossRetailerGroupResults", variables, ext, cookies)
        else:
            raise

    root = data.get("data", {}).get("searchCrossRetailerGroupResults", {}) or {}
    # signpostRetailerShopIds = ranked store order from Instacart (best first)
    signpost = root.get("signpostRetailerShopIds") or []
    best_shop_id = str(signpost[0]) if signpost else None
    r0 = (root.get("results") or [{}])[0]
    search_items_count = len(r0.get("items") or [])
    logger.info(
        "instacart_scraper: Search response results[0] items=%s itemIds=%s signpost[0]=%s",
        search_items_count,
        len(r0.get("itemIds") or []),
        best_shop_id,
    )

    results = root.get("results") or []
    shop_to_rid: dict[str, str] = {}
    for r in results:
        sid = str(r.get("shopId", ""))
        rid = r.get("retailerId")
        if sid and rid:
            shop_to_rid[sid] = str(rid)

    products = _parse_search_response(data)
    from_search = len(products)
    has_any_price = any(bool((p.get("price") or "").strip()) for p in products)
    if not products:
        for r in results:
            shop_id = str(r.get("shopId", ""))
            if best_shop_id and shop_id == best_shop_id:
                item_ids = r.get("itemIds") or []
                if item_ids:
                    products = _fetch_items_batch(item_ids[:limit], shop_id, postal_code)
                    for p in products:
                        p["retailer_id"] = shop_to_rid.get(shop_id, "")
                        p["shop_id"] = shop_id
                    break
        if not products:
            for r in results:
                shop_id = str(r.get("shopId", "") or (shop_ids[0] if shop_ids else "8621"))
                item_ids = r.get("itemIds") or []
                if item_ids:
                    products = _fetch_items_batch(item_ids[:limit], shop_id, postal_code)
                    for p in products:
                        p["retailer_id"] = shop_to_rid.get(shop_id, "")
                        p["shop_id"] = shop_id
                    best_shop_id = best_shop_id or shop_id
                    break
        products = products[:limit]
    elif not has_any_price and products and best_shop_id:
        item_ids = [p.get("id") for p in products if p.get("id")]
        if item_ids:
            items_products = _fetch_items_batch(item_ids[:limit], best_shop_id, postal_code)
            if items_products:
                products = items_products
                for p in products:
                    p["retailer_id"] = shop_to_rid.get(best_shop_id, "")
                    p["shop_id"] = best_shop_id

    if not best_shop_id and products:
        for r in results:
            if r.get("items"):
                best_shop_id = str(r.get("shopId", ""))
                break

    unique_retailer_ids = list({str(p.get("retailer_id", "")) for p in products if p.get("retailer_id")})
    rid_to_slug = _fetch_retailer_slugs_from_autosuggest(cookies, unique_retailer_ids, postal_code=postal_code)
    for p in products:
        p.setdefault("name", "")
        p.setdefault("price", "")
        p.setdefault("price_per_unit", "")
        rid = str(p.get("retailer_id", "")) if p.get("retailer_id") else ""
        p["retailer_slug"] = rid_to_slug.get(rid) or (f"unknown-{rid}" if rid else "")
        p.setdefault("retailer_id", "")
        p.setdefault("shop_id", "")

    best_retailer_id = shop_to_rid.get(best_shop_id or "") if best_shop_id else None
    best_retailer = rid_to_slug.get(best_retailer_id or "") or (f"unknown-{best_retailer_id}" if best_retailer_id else slug)
    logger.info(
        "instacart_scraper: search products=%s from=%s best_shop=%s retailer=%s",
        len(products),
        "Search" if from_search else "Items",
        best_shop_id,
        best_retailer,
    )
    return {
        "data": {
            "query": query,
            "products": products[:limit],
            "retailer": best_retailer,
            "postal_code": postal_code,
        },
        "status": "success",
    }


def get_product_details(item_id: str, shop_id: str, postal_code: str) -> dict[str, Any]:
    """
    Get product details via Items GraphQL operation (batch of 1).
    """
    items = _fetch_items_batch([item_id], shop_id, postal_code)
    if not items:
        return {
            "id": item_id,
            "name": "",
            "size": "",
            "brand": "",
            "price": "",
            "images": [],
            "rating": None,
            "product_id": item_id.split("-")[-1] if item_id else item_id,
            "description": "",
            "stock_level": "unknown",
            "dietary_attributes": [],
            "quantity_attributes": {},
            "nutritional_attributes": {},
        }
    p = items[0]
    img = p.get("image_url") or ""
    return {
        "id": p.get("id", item_id),
        "name": p.get("name", ""),
        "size": p.get("size", ""),
        "brand": p.get("brand", ""),
        "price": p.get("price", ""),
        "images": [img] if img else [],
        "rating": p.get("rating"),
        "product_id": p.get("product_id", item_id),
        "description": "",
        "stock_level": p.get("stock_status", "unknown"),
        "dietary_attributes": [],
        "quantity_attributes": {},
        "nutritional_attributes": {},
    }


def clear_cookie_cache(postal_code: str = "") -> None:
    """Clear cached cookies (e.g. after 403)."""
    try:
        paths = {_cookie_path_for_postal(postal_code), _cookie_path()}
        for p in paths:
            if p.exists():
                p.unlink()
                logger.info("instacart_scraper: cookie cache cleared %s", p)
    except Exception as e:
        logger.warning("instacart_scraper: failed to clear cookie cache: %s", e)
