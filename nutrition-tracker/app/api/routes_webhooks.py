from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from telegram import Update

from app.config import settings

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/telegram")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    application = getattr(request.app.state, "telegram_application", None)
    if application is None:
        raise HTTPException(
            status_code=503,
            detail="Webhook mode is disabled. Set BOT_WEBHOOK_MODE=true.",
        )

    data = await request.json()
    update_id = data.get("update_id")
    logger.debug("telegram_webhook_received", extra={"update_id": update_id})

    try:
        await application.process_update(Update.de_json(data, application.bot))
    except Exception as exc:
        logger.exception("telegram_webhook_process_failed", extra={"update_id": update_id, "error": str(exc)})

    return {"ok": True}
