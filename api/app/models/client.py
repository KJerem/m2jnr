"""Agrégat client : la personne qui confie ses véhicules au garage (données minimales, RGPD)."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, String, literal_column, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.vehicule import Vehicule


class Client(TimestampMixin, Base):
    __tablename__ = "client"
    __table_args__ = (
        CheckConstraint("char_length(btrim(nom)) > 0", name="nom_non_vide"),
        # Téléphone normalisé par l'application : 10 chiffres commençant par 0.
        CheckConstraint("telephone ~ '^0[1-9][0-9]{8}$'", name="telephone_normalise"),
        # Index non unique : deux clients peuvent partager un numéro (alerte, pas interdiction).
        Index("ix_client_telephone", "telephone"),
        # Recherche (story S1.3, migration 0013) : trigrammes du nom et du prénom sans accents
        # ni majuscules (fonction IMMUTABLE etabli_normaliser), et du téléphone.
        Index(
            "ix_client_nom_prenom_trgm",
            # Écrite comme PostgreSQL la restitue (comparaison d'Alembic) : même expression que
            # la migration, etabli_normaliser(nom || ' ' || coalesce(prenom, '')).
            literal_column(
                "etabli_normaliser((nom::text || ' '::text)"
                " || COALESCE(prenom, ''::character varying)::text)"
            ).label("nom_normalise"),
            postgresql_using="gin",
            postgresql_ops={"nom_normalise": "gin_trgm_ops"},
        ),
        Index(
            "ix_client_telephone_trgm",
            "telephone",
            postgresql_using="gin",
            postgresql_ops={"telephone": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str | None] = mapped_column(String(100))
    telephone: Mapped[str] = mapped_column(String(10), nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT())
    consentement_rappels: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Suppression d'un client refusée tant qu'il a des véhicules (ON DELETE RESTRICT).
    vehicules: Mapped[list["Vehicule"]] = relationship(
        back_populates="client", order_by="Vehicule.id", passive_deletes="all"
    )

    @property
    def nombre_vehicules(self) -> int:
        return len(self.vehicules)

    def __repr__(self) -> str:
        return f"<Client {self.id}>"
