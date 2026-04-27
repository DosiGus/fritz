import uuid

from sqlalchemy.orm import Session

from app.db.models import MealTemplate


class MealTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: uuid.UUID) -> list[MealTemplate]:
        return (
            self.db.query(MealTemplate)
            .filter(MealTemplate.user_id == user_id)
            .order_by(MealTemplate.template_name.asc())
            .all()
        )

    def get_by_name(self, user_id: uuid.UUID, template_name: str) -> MealTemplate | None:
        return (
            self.db.query(MealTemplate)
            .filter(MealTemplate.user_id == user_id, MealTemplate.template_name.ilike(template_name))
            .first()
        )

    def create(
        self,
        user_id: uuid.UUID,
        template_name: str,
        total_kcal: float | None = None,
        total_protein: float | None = None,
        total_carbs: float | None = None,
        total_fat: float | None = None,
    ) -> MealTemplate:
        template = MealTemplate(
            user_id=user_id,
            template_name=template_name,
            total_kcal=total_kcal,
            total_protein=total_protein,
            total_carbs=total_carbs,
            total_fat=total_fat,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def delete(self, template: MealTemplate) -> None:
        self.db.delete(template)
        self.db.commit()
