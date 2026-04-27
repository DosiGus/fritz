import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.config import settings

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/telegram")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    logger.debug("telegram_webhook_received", extra={"update_id": data.get("update_id")})

    # The telegram-bot library processes updates directly;
    # in webhook mode the app object handles routing via the application.process_update path.
    return {"ok": True}
