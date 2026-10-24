"""Ponts élévateurs de l'atelier (Pont 1, Pont 2…) : un rendez-vous occupe un pont."""

from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Pont(TimestampMixin, Base):
    __tablename__ = "pont"
    __table_args__ = (CheckConstraint("char_length(btrim(nom)) > 0", name="nom_non_vide"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    actif: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    def __repr__(self) -> str:
        return f"<Pont {self.id} {self.nom}>"
