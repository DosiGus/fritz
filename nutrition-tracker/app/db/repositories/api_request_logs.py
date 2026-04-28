from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import ApiRequestLog


class ApiRequestLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        service: str,
        endpoint: str,
        method: str = "GET",
        status_code: int | None = None,
        success: bool = True,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> ApiRequestLog:
        log = ApiRequestLog(
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            success=success,
            duration_ms=duration_ms,
            error=error,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def count_errors_since(self, service: str, since: datetime) -> int:
        return (
            self.db.query(ApiRequestLog)
            .filter(
                ApiRequestLog.service == service,
                ApiRequestLog.success == False,  # noqa: E712
                ApiRequestLog.created_at >= since,
            )
            .count()
        )

    def count_total_errors_since(self, since: datetime) -> int:
        return (
            self.db.query(ApiRequestLog)
            .filter(
                ApiRequestLog.success == False,  # noqa: E712
                ApiRequestLog.created_at >= since,
            )
            .count()
        )

    def list_recent_errors(self, limit: int = 50) -> list[ApiRequestLog]:
        return (
            self.db.query(ApiRequestLog)
            .filter(ApiRequestLog.success == False)  # noqa: E712
            .order_by(ApiRequestLog.created_at.desc())
            .limit(limit)
            .all()
        )
