"""Nominatim geocoding client with caching, rate-limiting, and graceful failure handling.

SIH26189GREEN — AI-Powered Criminal Network Analysis System
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "NEXUS-Criminal-Network-Analysis/1.0 (SIH26189GREEN)"
DEFAULT_TIMEOUT_SEC = 3.0

# In-memory LRU-style cache to respect OpenStreetMap Nominatim 1 request/second usage policy
_GEOCODE_CACHE: dict[str, dict[str, Any]] = {}
_LAST_REQUEST_TIME: float = 0.0


def geocode_location(
    location_name: str,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    client: httpx.Client | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    """Geocode a place name into latitude/longitude with graceful degradation.

    Guarantees:
    - Never crashes or raises unhandled exceptions.
    - If geocoding fails, times out, or network is unavailable, returns a structured
      degraded response with location fields as None / 'unknown' and logs a clear warning.
    - Caches responses in-memory.
    - Respects Nominatim rate-limiting policy.

    Returns:
        dict with keys:
            - status: 'ok', 'not_found', 'unavailable', or 'invalid_input'
            - location_name: str
            - latitude: float | None
            - longitude: float | None
            - display_name: str | None
            - error: str | None
    """
    global _LAST_REQUEST_TIME

    if not location_name or not location_name.strip():
        return {
            "status": "invalid_input",
            "location_name": "",
            "latitude": None,
            "longitude": None,
            "display_name": None,
            "error": "Empty location name provided",
        }

    clean_name = location_name.strip()
    cache_key = clean_name.lower()
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # Enforce Nominatim 1 request/second policy
    now = time.time()
    elapsed = now - _LAST_REQUEST_TIME
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    params = {
        "q": clean_name,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    own_client = client is None
    http_client = client or httpx.Client(timeout=timeout_sec)

    try:
        _LAST_REQUEST_TIME = time.time()
        response = http_client.get(NOMINATIM_BASE_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list) or len(data) == 0:
            result = {
                "status": "not_found",
                "location_name": clean_name,
                "latitude": None,
                "longitude": None,
                "display_name": None,
                "error": None,
            }
            _GEOCODE_CACHE[cache_key] = result
            return result

        top_match = data[0]
        result = {
            "status": "ok",
            "location_name": clean_name,
            "latitude": float(top_match["lat"]),
            "longitude": float(top_match["lon"]),
            "display_name": top_match.get("display_name"),
            "error": None,
        }
        _GEOCODE_CACHE[cache_key] = result
        return result

    except httpx.TimeoutException as timeout_err:
        logger.warning(
            "Geocoding service timed out for location '%s' after %ss: %s",
            clean_name,
            timeout_sec,
            timeout_err,
        )
        return {
            "status": "unavailable",
            "location_name": clean_name,
            "latitude": None,
            "longitude": None,
            "display_name": None,
            "error": f"Geocoding request timed out after {timeout_sec}s",
        }
    except (httpx.ConnectError, httpx.NetworkError) as net_err:
        logger.warning(
            "Geocoding service unreachable for location '%s': %s",
            clean_name,
            net_err,
        )
        return {
            "status": "unavailable",
            "location_name": clean_name,
            "latitude": None,
            "longitude": None,
            "display_name": None,
            "error": f"Network error connecting to geocoding service: {type(net_err).__name__}",
        }
    except Exception as exc:
        logger.warning(
            "Geocoding failed gracefully for location '%s': %s (%s)",
            clean_name,
            exc,
            type(exc).__name__,
        )
        return {
            "status": "unavailable",
            "location_name": clean_name,
            "latitude": None,
            "longitude": None,
            "display_name": None,
            "error": f"Geocoding failure: {str(exc)}",
        }
    finally:
        if own_client:
            http_client.close()


def enrich_entity_with_geocoding(entity: dict[str, Any]) -> dict[str, Any]:
    """Enrich a LOCATION entity with geocoding coordinates if applicable.

    If geocoding fails or is unavailable, retains all existing entity fields
    and annotates geocoding status as 'unknown' without crashing.
    """
    if entity.get("entity_type") != "LOCATION":
        return entity

    location_name = entity.get("name") or entity.get("canonical_name")
    if not location_name:
        return entity

    geo_res = geocode_location(location_name)
    metadata = dict(entity.get("metadata") or {})

    if geo_res.get("status") == "ok":
        metadata["coordinates"] = {
            "lat": geo_res["latitude"],
            "lon": geo_res["longitude"],
        }
        metadata["geocoded_address"] = geo_res["display_name"]
        metadata["geocoding_status"] = "resolved"
    else:
        metadata["coordinates"] = None
        metadata["geocoding_status"] = "unknown"
        metadata["geocoding_reason"] = geo_res.get("error") or geo_res.get("status")

    entity["metadata"] = metadata
    return entity
