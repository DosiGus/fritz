from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


class AuditEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        event_type: str,
        payload: dict | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            user_id=user_id,
            event_type=event_type,
            payload=payload,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_by_type(self, event_type: str, limit: int = 100) -> list[AuditEvent]:
        return (
            self.db.query(AuditEvent)
            .filter(AuditEvent.event_type == event_type)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_since(self, since: datetime) -> int:
        return self.db.query(AuditEvent).filter(AuditEvent.created_at >= since).count()
