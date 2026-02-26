"""Location/geolocation from client IP for scraper postal code."""

import httpx

from fastapi import APIRouter, Request

from app.config import settings
from app.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

GEO_URL = "http://ip-api.com/json"
GEO_TIMEOUT = 5.0
DEFAULT_US_POSTAL = "10001"


def _client_ip(request: Request) -> str:
    """Extract client IP from request (respects X-Forwarded-For, X-Real-IP)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host or "127.0.0.1"
    return "127.0.0.1"


@router.get("/location")
def get_location(request: Request) -> dict:
    """
    Get postal code from client IP for Instacart scraping.
    If outside US: returns error + default postal (10001) so app can still function.
    """
    client_ip = _client_ip(request)
    logger.info("location.request client_ip=%s", client_ip)

    try:
        resp = httpx.get(
            f"{GEO_URL}/{client_ip}",
            params={"fields": "status,message,countryCode,zip"},
            timeout=GEO_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("location.geo_failed ip=%s error=%s", client_ip, e)
        return {
            "postal_code": getattr(settings, "default_postal_code", DEFAULT_US_POSTAL),
            "country_code": None,
            "in_us": False,
            "error": "Could not determine location. Using default US postal code.",
        }

    if data.get("status") != "success":
        msg = data.get("message", "unknown")
        logger.info("location.geo_invalid ip=%s message=%s", client_ip, msg)
        return {
            "postal_code": getattr(settings, "default_postal_code", DEFAULT_US_POSTAL),
            "country_code": None,
            "in_us": False,
            "error": f"Location unavailable ({msg}). Using default US postal code.",
        }

    country = data.get("countryCode", "")
    zip_val = data.get("zip") or ""
    in_us = (country or "").upper() == "US"

    if in_us and zip_val:
        return {
            "postal_code": str(zip_val).strip()[:10],
            "country_code": country,
            "in_us": True,
        }

    if not in_us:
        logger.info("location.outside_us ip=%s country=%s", client_ip, country)
        return {
            "postal_code": getattr(settings, "default_postal_code", DEFAULT_US_POSTAL),
            "country_code": country,
            "in_us": False,
            "error": "Service available in US only. Using default postal code.",
        }

    # US but no zip (e.g. mobile, some ISPs)
    return {
        "postal_code": getattr(settings, "default_postal_code", DEFAULT_US_POSTAL),
        "country_code": country,
        "in_us": True,
        "error": "Postal code unavailable. Using default.",
    }
