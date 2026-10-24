"""Agrégat client : la personne qui confie ses véhicules au garage (données minimales, RGPD)."""

from sqlalchemy import Boolean, CheckConstraint, Index, String, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Client(TimestampMixin, Base):
    __tablename__ = "client"
    __table_args__ = (
        CheckConstraint("char_length(btrim(nom)) > 0", name="nom_non_vide"),
        # Téléphone normalisé par l'application : 10 chiffres commençant par 0.
        CheckConstraint("telephone ~ '^0[1-9][0-9]{8}$'", name="telephone_normalise"),
        # Index non unique : deux clients peuvent partager un numéro (alerte, pas interdiction).
        Index("ix_client_telephone", "telephone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str | None] = mapped_column(String(100))
    telephone: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT())
    consentement_rappels: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    def __repr__(self) -> str:
        return f"<Client {self.id}>"
