import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ConversationState


class ConversationStateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_for_user(self, user_id: uuid.UUID) -> ConversationState | None:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(ConversationState)
            .filter(ConversationState.user_id == user_id, ConversationState.expires_at > now)
            .order_by(ConversationState.created_at.desc())
            .first()
        )

    def create(
        self,
        user_id: uuid.UUID,
        state_type: str,
        payload: dict,
        expires_at: datetime,
    ) -> ConversationState:
        state = ConversationState(
            user_id=user_id,
            state_type=state_type,
            payload=payload,
            expires_at=expires_at,
        )
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        return state

    def delete_for_user(self, user_id: uuid.UUID) -> int:
        deleted = (
            self.db.query(ConversationState)
            .filter(ConversationState.user_id == user_id)
            .delete()
        )
        self.db.commit()
        return deleted

    def delete_expired(self) -> int:
        now = datetime.now(timezone.utc)
        deleted = (
            self.db.query(ConversationState)
            .filter(ConversationState.expires_at <= now)
            .delete()
        )
        self.db.commit()
        return deleted

    def get_by_id(self, state_id: uuid.UUID) -> ConversationState | None:
        return self.db.query(ConversationState).filter(ConversationState.id == state_id).first()
