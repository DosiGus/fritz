import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.api.routes_health import router as health_router
from app.api.routes_admin import router as admin_router, public_router as admin_public_router
from app.api.routes_webhooks import router as webhook_router
from app.config import settings
from app.logging_config import setup_logging

setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
    )


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    fastapi_app.state.telegram_application = None
    if settings.bot_webhook_mode and settings.telegram_bot_token:
        from app.bot.telegram_app import build_application

        application = build_application()
        await application.initialize()
        await application.start()
        fastapi_app.state.telegram_application = application
        logger.info("telegram_webhook_mode_started")

    logger.info("app_startup", extra={"env": settings.app_env})
    try:
        yield
    finally:
        application = fastapi_app.state.telegram_application
        if application is not None:
            await application.stop()
            await application.shutdown()
            logger.info("telegram_webhook_mode_stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(admin_public_router)
app.include_router(admin_router, prefix="/admin")
app.include_router(webhook_router, prefix="/webhook")
