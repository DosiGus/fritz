from __future__ import annotations

import logging
import time

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db.repositories.api_request_logs import ApiRequestLogRepository
from app.utils.rate_limit import SimpleRateLimiter

logger = logging.getLogger(__name__)

_BASE = "https://api.nal.usda.gov/fdc/v1"

# USDA FDC: no hard public limit stated, but 3 500/hour is a reasonable ceiling
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
    extra = {
        "service": "usda_fdc",
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
            service="usda_fdc",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            success=success,
            duration_ms=round(duration_ms, 1),
            error=error,
        )
    except Exception as exc:
        logger.warning("api_request_log_write_failed", extra={"service": "usda_fdc", "error": str(exc)})


class UsdaFdcClient:
    def __init__(self, db: Session | None = None) -> None:
        self._db = db
        self._client = httpx.Client(
            base_url=_BASE,
            params={"api_key": settings.usda_api_key},
            timeout=settings.usda_timeout,
        )

    def search(self, query: str, page_size: int = 5, data_type: list[str] | None = None) -> list[dict]:
        endpoint = "/foods/search"
        payload: dict = {"query": query, "pageSize": page_size}
        if data_type:
            payload["dataType"] = data_type
        _rate_limiter.acquire()
        t0 = time.monotonic()
        try:
            response = self._client.post(endpoint, json=payload)
            response.raise_for_status()
            duration_ms = (time.monotonic() - t0) * 1000
            _log_request(self._db, endpoint, "POST", response.status_code, True, duration_ms)
            return response.json().get("foods", [])
        except httpx.HTTPError as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
            _log_request(self._db, endpoint, "POST", status, False, duration_ms, str(exc))
            logger.warning("usda_search_failed", extra={"query": query, "error": str(exc)})
            return []

    def get_food(self, fdc_id: int) -> dict | None:
        endpoint = f"/food/{fdc_id}"
        _rate_limiter.acquire()
        t0 = time.monotonic()
        try:
            response = self._client.get(endpoint)
            response.raise_for_status()
            duration_ms = (time.monotonic() - t0) * 1000
            _log_request(self._db, endpoint, "GET", response.status_code, True, duration_ms)
            return response.json()
        except httpx.HTTPError as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
            _log_request(self._db, endpoint, "GET", status, False, duration_ms, str(exc))
            logger.warning("usda_get_food_failed", extra={"fdc_id": fdc_id, "error": str(exc)})
            return None

    def close(self) -> None:
        self._client.close()
