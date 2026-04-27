import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://world.openfoodfacts.org"


class OpenFoodFactsClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=_BASE,
            headers={"User-Agent": settings.open_food_facts_user_agent},
            timeout=settings.open_food_facts_timeout,
        )

    def search_by_name(self, query: str, language: str = "de", page_size: int = 5) -> list[dict]:
        try:
            response = self._client.get(
                "/cgi/search.pl",
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
            data = response.json()
            return data.get("products", [])
        except httpx.HTTPError as exc:
            logger.warning("off_search_failed", extra={"query": query, "error": str(exc)})
            return []

    def get_by_barcode(self, barcode: str) -> dict | None:
        try:
            response = self._client.get(f"/api/v0/product/{barcode}.json")
            response.raise_for_status()
            data = response.json()
            if data.get("status") == 1:
                return data.get("product")
            return None
        except httpx.HTTPError as exc:
            logger.warning("off_barcode_failed", extra={"barcode": barcode, "error": str(exc)})
            return None

    def close(self) -> None:
        self._client.close()
