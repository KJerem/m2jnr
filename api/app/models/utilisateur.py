"""Agrégat utilisateur : employé du garage (gérant ou mécanicien)."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Integer, String, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Role(enum.StrEnum):
    GERANT = "gerant"
    MECANICIEN = "mecanicien"


class Utilisateur(TimestampMixin, Base):
    __tablename__ = "utilisateur"
    __table_args__ = (CheckConstraint("tentatives_echouees >= 0", name="tentatives_positives"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            name="role_utilisateur",
            values_callable=lambda roles: [r.value for r in roles],
        ),
        nullable=False,
    )
    actif: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    tentatives_echouees: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bloque_jusqu_a: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Utilisateur {self.id} {self.role.value}>"
