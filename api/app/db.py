"""Moteur SQLAlchemy, session par requête et base déclarative."""

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import DateTime, MetaData, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings

# Conventions de nommage : des noms de contraintes stables pour Alembic.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête, validée ou annulée en fin de requête.

    Ne pas l'utiliser directement : passer par `DbSession`, qui garantit le commit avant
    l'envoi de la réponse."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Portée « function » : le code après le `yield` (commit ou rollback) s'exécute dès que la
# route a rendu sa valeur, AVANT l'envoi du statut et du corps. Avec la portée par défaut
# (« request »), FastAPI validerait la transaction après l'envoi de la réponse : un 201
# pourrait annoncer une donnée qui n'est pas encore (ou jamais) en base. Toutes les routes et
# dépendances utilisent ce même alias, donc partagent la même session dans une requête.
DbSession = Annotated[Session, Depends(get_db, scope="function")]
