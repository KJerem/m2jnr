"""Sonde de santé : l'application répond et la base est joignable."""

from fastapi import APIRouter
from sqlalchemy import text

from app.db import DbSession

router = APIRouter(tags=["santé"])


@router.get("/health")
def health(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"statut": "ok", "base": "ok"}
