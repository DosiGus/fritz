import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/live")
def live_check():
    return {"status": "ok"}


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    checks = {"database": False, "redis": False}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})

    client = redis.from_url(settings.redis_url)
    try:
        client.ping()
        checks["redis"] = True
    except redis.RedisError:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    finally:
        client.close()

    return {"status": "ready", "checks": checks}


@router.get("/")
def root():
    return {"service": "telegram-nutrition-tracker", "status": "running"}
