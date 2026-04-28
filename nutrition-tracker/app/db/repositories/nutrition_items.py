from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import FoodAlias, NutritionItem


class NutritionItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_canonical_name(self, canonical_name: str) -> NutritionItem | None:
        return (
            self.db.query(NutritionItem)
            .filter(NutritionItem.canonical_name.ilike(canonical_name))
            .first()
        )

    def get_by_barcode(self, barcode: str) -> NutritionItem | None:
        return self.db.query(NutritionItem).filter(NutritionItem.barcode == barcode).first()

    def create(
        self,
        canonical_name: str,
        kcal_100g: float | None = None,
        protein_100g: float | None = None,
        carbs_100g: float | None = None,
        fat_100g: float | None = None,
        source: str | None = None,
        source_id: str | None = None,
        brand: str | None = None,
        barcode: str | None = None,
        verified: bool = False,
    ) -> NutritionItem:
        item = NutritionItem(
            canonical_name=canonical_name,
            kcal_100g=kcal_100g,
            protein_100g=protein_100g,
            carbs_100g=carbs_100g,
            fat_100g=fat_100g,
            source=source,
            source_id=source_id,
            brand=brand,
            barcode=barcode,
            verified=verified,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def upsert_from_api(
        self,
        canonical_name: str,
        source: str,
        source_id: str,
        **kwargs,
    ) -> NutritionItem:
        item = (
            self.db.query(NutritionItem)
            .filter(NutritionItem.source == source, NutritionItem.source_id == source_id)
            .first()
        )
        if item:
            for key, value in kwargs.items():
                setattr(item, key, value)
            self.db.commit()
            self.db.refresh(item)
            return item
        return self.create(canonical_name=canonical_name, source=source, source_id=source_id, **kwargs)

    def list_unverified(self, limit: int = 50) -> list[NutritionItem]:
        return (
            self.db.query(NutritionItem)
            .filter(NutritionItem.verified == False)  # noqa: E712
            .limit(limit)
            .all()
        )

    def verify(self, item: NutritionItem) -> NutritionItem:
        item.verified = True
        self.db.commit()
        self.db.refresh(item)
        return item


class FoodAliasRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_alias(self, alias: str, language: str = "de") -> FoodAlias | None:
        return (
            self.db.query(FoodAlias)
            .filter(FoodAlias.alias.ilike(alias), FoodAlias.language == language)
            .first()
        )

    def create(
        self,
        alias: str,
        canonical_name: str,
        language: str = "de",
        confidence: float = 0.8,
    ) -> FoodAlias:
        fa = FoodAlias(alias=alias, canonical_name=canonical_name, language=language, confidence=confidence)
        self.db.add(fa)
        self.db.commit()
        self.db.refresh(fa)
        return fa

    def list_all(self) -> list[FoodAlias]:
        return self.db.query(FoodAlias).all()
