import logging

from app.db.session import SessionLocal
from app.services.audit_service import AuditService
from app.services.nutrition_matcher import match

logger = logging.getLogger(__name__)


def process_nutrition_lookup(canonical_name: str, user_id: str) -> None:
    """Background job for async nutrition API lookups."""
    with SessionLocal() as db:
        result = match(canonical_name, db=db)
        AuditService(db).log(
            event_type="nutrition_lookup_job_completed",
            payload={
                "canonical_name": canonical_name,
                "user_id": user_id,
                "matched": result.model_dump() if result else None,
            },
        )
    logger.info("nutrition_lookup_job_completed", extra={"canonical_name": canonical_name})
