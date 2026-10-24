"""Agrégat facture : la copie figée d'un devis au moment de l'émission (story S4.3).

Numéro « F-AAAA-nnn » continu et sans trou (compteur de type FACTURE, verrouillé dans la
transaction d'émission). Le client, le véhicule, les mentions du garage, les lignes et les
montants sont recopiés : modifier ensuite la fiche du client ou du véhicule ne change pas une
facture émise, et son PDF reste identique.

Une facture ne se modifie ni ne se supprime : des triggers PostgreSQL refusent UPDATE, DELETE
et TRUNCATE sur `facture` et `ligne_facture` (SQLSTATE ET001, « facture immuable »), même en
dehors de l'API ; une ligne ne s'ajoute que dans la transaction qui crée sa facture
(migration 0011). Les relations ci-dessous ne propagent donc aucune suppression.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.devis import ENUM_TYPE_LIGNE, TypeLigne

if TYPE_CHECKING:
    from app.models.devis import Devis
    from app.models.ordre_travail import OrdreTravail
    from app.models.utilisateur import Utilisateur

# « F-2026-001 » : trois chiffres au moins, davantage au-delà de 999.
REGEX_NUMERO_FACTURE_SQL = "^F-[0-9]{4}-[0-9]{3,}$"
# Code d'erreur des triggers d'immuabilité (classe « ET », propre à l'application).
SQLSTATE_FACTURE_IMMUABLE = "ET001"


class Facture(Base):
    __tablename__ = "facture"
    __table_args__ = (
        CheckConstraint(f"numero ~ '{REGEX_NUMERO_FACTURE_SQL}'", name="numero_format"),
        CheckConstraint("taux_tva_bp >= 0 AND taux_tva_bp <= 10000", name="taux_tva_borne"),
        CheckConstraint("total_ht_centimes >= 0", name="total_ht_positif"),
        CheckConstraint("total_tva_centimes >= 0", name="total_tva_positif"),
        CheckConstraint("total_ttc_centimes >= 0", name="total_ttc_positif"),
        CheckConstraint(
            "total_ttc_centimes = total_ht_centimes + total_tva_centimes", name="ttc_coherent"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # Un devis est facturé au plus une fois.
    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    ordre_travail_id: Mapped[int] = mapped_column(
        ForeignKey("ordre_travail.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    emise_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    echeance: Mapped[date] = mapped_column(Date, nullable=False)
    # {nom, prenom, telephone, email} au moment de l'émission.
    client_fige: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # {immatriculation, marque, modele, kilometrage}.
    vehicule_fige: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Mentions du garage : raison sociale, adresse, SIRET, TVA intracommunautaire, capital,
    # RCS, téléphone, e-mail.
    garage_fige: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    taux_tva_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    total_ht_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_tva_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_ttc_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cree_par: Mapped[int] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), nullable=False
    )
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    devis: Mapped["Devis"] = relationship(back_populates="facture")
    ordre: Mapped["OrdreTravail"] = relationship()
    createur: Mapped["Utilisateur"] = relationship()
    lignes: Mapped[list["LigneFacture"]] = relationship(
        back_populates="facture",
        order_by="(LigneFacture.position, LigneFacture.id)",
        passive_deletes="all",
    )

    def __repr__(self) -> str:
        return f"<Facture {self.id} {self.numero}>"


class LigneFacture(Base):
    """Ligne recopiée du devis à l'émission ; jamais modifiée ni supprimée."""

    __tablename__ = "ligne_facture"
    __table_args__ = (
        CheckConstraint("quantite > 0", name="quantite_positive"),
        CheckConstraint("prix_unitaire_ht_centimes >= 0", name="prix_positif"),
        CheckConstraint("total_ht_centimes >= 0", name="total_positif"),
        CheckConstraint("char_length(btrim(designation)) > 0", name="designation_non_vide"),
        CheckConstraint("position >= 0", name="position_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    facture_id: Mapped[int] = mapped_column(
        ForeignKey("facture.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[TypeLigne] = mapped_column(ENUM_TYPE_LIGNE, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(40))
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    quantite: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    prix_unitaire_ht_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_ht_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    facture: Mapped[Facture] = relationship(back_populates="lignes")

    def __repr__(self) -> str:
        return f"<LigneFacture {self.id} facture {self.facture_id}>"
