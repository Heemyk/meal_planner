"""Tests for location/geolocation API."""

import respx
from httpx import Response


@respx.mock
def test_location_us_success(client):
    respx.get("http://ip-api.com/json/1.2.3.4").mock(
        return_value=Response(200, json={
            "status": "success",
            "countryCode": "US",
            "zip": "10001",
        })
    )
    response = client.get(
        "/api/location",
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["postal_code"] == "10001"
    assert data["country_code"] == "US"
    assert data["in_us"] is True
    assert "error" not in data or data.get("error") is None


@respx.mock
def test_location_outside_us(client):
    respx.get("http://ip-api.com/json/5.6.7.8").mock(
        return_value=Response(200, json={
            "status": "success",
            "countryCode": "GB",
            "zip": "SW1A 1AA",
        })
    )
    response = client.get(
        "/api/location",
        headers={"X-Forwarded-For": "5.6.7.8"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["in_us"] is False
    assert "error" in data
    assert "postal_code" in data
    assert data["country_code"] == "GB"


@respx.mock
def test_location_geo_failure(client):
    respx.get("http://ip-api.com/json/127.0.0.1").mock(
        return_value=Response(500)
    )
    response = client.get("/api/location")
    assert response.status_code == 200
    data = response.json()
    assert data["in_us"] is False
    assert "error" in data
    assert "postal_code" in data


@respx.mock
def test_location_private_range(client):
    respx.get("http://ip-api.com/json/127.0.0.1").mock(
        return_value=Response(200, json={
            "status": "fail",
            "message": "private range",
        })
    )
    response = client.get("/api/location")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert "postal_code" in data


@respx.mock
def test_location_extracts_forwarded_ip(client):
    respx.get("http://ip-api.com/json/9.9.9.9").mock(
        return_value=Response(200, json={
            "status": "success",
            "countryCode": "US",
            "zip": "94043",
        })
    )
    response = client.get(
        "/api/location",
        headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["postal_code"] == "94043"


@respx.mock
def test_location_cloudflare_cf_connecting_ip(client):
    """When behind Cloudflare, CF-Connecting-IP has the real visitor IP."""
    respx.get("http://ip-api.com/json/203.0.113.50").mock(
        return_value=Response(200, json={
            "status": "success",
            "countryCode": "US",
            "zip": "10001",
        })
    )
    response = client.get(
        "/api/location",
        headers={"CF-Connecting-IP": "203.0.113.50"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["postal_code"] == "10001"
