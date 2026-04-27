import logging

import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.api.routes_health import router as health_router
from app.api.routes_admin import router as admin_router
from app.api.routes_webhooks import router as webhook_router
from app.config import settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
    )

app = FastAPI(title=settings.app_name, version="0.1.0")

app.include_router(health_router)
app.include_router(admin_router, prefix="/admin")
app.include_router(webhook_router, prefix="/webhook")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("app_startup", extra={"env": settings.app_env})
