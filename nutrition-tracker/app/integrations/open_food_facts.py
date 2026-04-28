from __future__ import annotations

import logging
import time

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories.api_request_logs import ApiRequestLogRepository
from app.utils.rate_limit import SimpleRateLimiter

logger = logging.getLogger(__name__)

_BASE = "https://world.openfoodfacts.org"

# 10 requests per 60 s — stays well within public API fair-use limits
_rate_limiter = SimpleRateLimiter(max_calls=10, period=60.0)


def _log_request(
    db: Session | None,
    endpoint: str,
    method: str,
    status_code: int | None,
    success: bool,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Fire-and-forget structured log plus optional persistent request log."""
    extra = {
        "service": "open_food_facts",
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "success": success,
        "duration_ms": round(duration_ms, 1),
    }
    if error:
        extra["error"] = error
    if success:
        logger.debug("api_request", extra=extra)
    else:
        logger.warning("api_request_error", extra=extra)
    if db is None:
        return
    try:
        ApiRequestLogRepository(db).create(
            service="open_food_facts",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            success=success,
            duration_ms=round(duration_ms, 1),
            error=error,
        )
    except Exception as exc:
        logger.warning("api_request_log_write_failed", extra={"service": "open_food_facts", "error": str(exc)})


class OpenFoodFactsClient:
    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._client = httpx.Client(
            base_url=_BASE,
            headers={"User-Agent": settings.open_food_facts_user_agent},
            timeout=settings.open_food_facts_timeout,
        )

    def search_by_name(self, query: str, language: str = "de", page_size: int = 5) -> list[dict]:
        endpoint = "/cgi/search.pl"
        _rate_limiter.acquire()
        t0 = time.monotonic()
        try:
            response = self._client.get(
                endpoint,
                params={
                    "search_terms": query,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": page_size,
                    "lc": language,
                },
            )
            response.raise_for_status()
            duration_ms = (time.monotonic() - t0) * 1000
            _log_request(self._db, endpoint, "GET", response.status_code, True, duration_ms)
            data = response.json()
            return data.get("products", [])
        except httpx.HTTPError as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
            _log_request(self._db, endpoint, "GET", status, False, duration_ms, str(exc))
            logger.warning("off_search_failed", extra={"query": query, "error": str(exc)})
            return []

    def get_by_barcode(self, barcode: str) -> dict | None:
        endpoint = f"/api/v0/product/{barcode}.json"
        _rate_limiter.acquire()
        t0 = time.monotonic()
        try:
            response = self._client.get(endpoint)
            response.raise_for_status()
            duration_ms = (time.monotonic() - t0) * 1000
            _log_request(self._db, endpoint, "GET", response.status_code, True, duration_ms)
            data = response.json()
            if data.get("status") == 1:
                return data.get("product")
            return None
        except httpx.HTTPError as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
            _log_request(self._db, endpoint, "GET", status, False, duration_ms, str(exc))
            logger.warning("off_barcode_failed", extra={"barcode": barcode, "error": str(exc)})
            return None

    def close(self) -> None:
        self._client.close()
