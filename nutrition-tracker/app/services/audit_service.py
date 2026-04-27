import logging
import uuid

from sqlalchemy.orm import Session

from app.db.repositories.audit_events import AuditEventRepository

logger = logging.getLogger(__name__)


class AuditService:
    """Write-only audit log. Never reads. Never raises."""

    def __init__(self, db: Session) -> None:
        self._repo = AuditEventRepository(db)

    def log(
        self,
        event_type: str,
        payload: dict | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        try:
            self._repo.create(event_type=event_type, payload=payload, user_id=user_id)
            logger.debug("audit_event", extra={"event_type": event_type, "user_id": str(user_id)})
        except Exception as exc:
            logger.error("audit_write_failed", extra={"event_type": event_type, "error": str(exc)})
