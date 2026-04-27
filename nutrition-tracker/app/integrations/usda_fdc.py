import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.nal.usda.gov/fdc/v1"


class UsdaFdcClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=_BASE,
            params={"api_key": settings.usda_api_key},
            timeout=settings.usda_timeout,
        )

    def search(self, query: str, page_size: int = 5, data_type: list[str] | None = None) -> list[dict]:
        payload: dict = {"query": query, "pageSize": page_size}
        if data_type:
            payload["dataType"] = data_type
        try:
            response = self._client.post("/foods/search", json=payload)
            response.raise_for_status()
            return response.json().get("foods", [])
        except httpx.HTTPError as exc:
            logger.warning("usda_search_failed", extra={"query": query, "error": str(exc)})
            return []

    def get_food(self, fdc_id: int) -> dict | None:
        try:
            response = self._client.get(f"/food/{fdc_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            logger.warning("usda_get_food_failed", extra={"fdc_id": fdc_id, "error": str(exc)})
            return None

    def close(self) -> None:
        self._client.close()
