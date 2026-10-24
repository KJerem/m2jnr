"""Agrégat devis : le chiffrage d'un ordre de travail en lignes « pièce » et « main-d'œuvre ».

Montants en centimes (entiers) ; quantité en décimal à deux chiffres après la virgule
(0,5 h, 1,25 l). Le total de chaque ligne et les totaux du devis (HT, TVA, TTC) sont calculés
par app/services/calcul_devis.py et enregistrés : la facture (story S4.3) recopie exactement
ce qui a été présenté au client.

Le statut du devis (brouillon, envoyé, accepté, refusé) arrive avec la story S4.2 : un OT
peut déjà porter plusieurs devis (un devis refusé sera remplacé par un nouveau), le devis
« courant » est le plus récent.
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.facture import Facture
    from app.models.ordre_travail import OrdreTravail
    from app.models.utilisateur import Utilisateur

# 20 % exprimé en points de base (1 bp = 0,01 %).
TAUX_TVA_NORMAL_BP = 2000


class TypeLigne(enum.StrEnum):
    PIECE = "piece"
    MAIN_OEUVRE = "main_oeuvre"


ENUM_TYPE_LIGNE = Enum(
    TypeLigne,
    name="type_ligne",
    values_callable=lambda types: [t.value for t in types],
)


class Devis(Base):
    __tablename__ = "devis"
    __table_args__ = (
        CheckConstraint("taux_tva_bp >= 0 AND taux_tva_bp <= 10000", name="taux_tva_borne"),
        CheckConstraint("total_ht_centimes >= 0", name="total_ht_positif"),
        CheckConstraint("total_tva_centimes >= 0", name="total_tva_positif"),
        CheckConstraint("total_ttc_centimes >= 0", name="total_ttc_positif"),
        CheckConstraint(
            "total_ttc_centimes = total_ht_centimes + total_tva_centimes", name="ttc_coherent"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ordre_travail_id: Mapped[int] = mapped_column(
        ForeignKey("ordre_travail.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    taux_tva_bp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=TAUX_TVA_NORMAL_BP,
        server_default=text(str(TAUX_TVA_NORMAL_BP)),
    )
    total_ht_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_tva_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_ttc_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cree_par: Mapped[int] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), nullable=False
    )
    # Horodatage de l'horloge injectée (app.clock.get_now), renseigné par le service.
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modifie_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ordre: Mapped["OrdreTravail"] = relationship()
    createur: Mapped["Utilisateur"] = relationship()
    lignes: Mapped[list["LigneDevis"]] = relationship(
        back_populates="devis",
        order_by="(LigneDevis.position, LigneDevis.id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # Facture émise à partir de ce devis (au plus une, story S4.3) : jamais supprimée ni
    # modifiée par l'ORM (la base refuse UPDATE et DELETE sur une facture).
    facture: Mapped["Facture | None"] = relationship(
        back_populates="devis", uselist=False, passive_deletes="all"
    )

    def __repr__(self) -> str:
        return f"<Devis {self.id} OT {self.ordre_travail_id}>"


class LigneDevis(Base):
    """Ligne d'un devis, supprimée avec lui. Remplacée en bloc à chaque modification."""

    __tablename__ = "ligne_devis"
    __table_args__ = (
        CheckConstraint("quantite > 0", name="quantite_positive"),
        CheckConstraint("prix_unitaire_ht_centimes >= 0", name="prix_positif"),
        CheckConstraint("total_ht_centimes >= 0", name="total_positif"),
        CheckConstraint("char_length(btrim(designation)) > 0", name="designation_non_vide"),
        CheckConstraint("position >= 0", name="position_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    devis_id: Mapped[int] = mapped_column(
        ForeignKey("devis.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[TypeLigne] = mapped_column(ENUM_TYPE_LIGNE, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(40))
    designation: Mapped[str] = mapped_column(String(200), nullable=False)
    quantite: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    prix_unitaire_ht_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_ht_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    devis: Mapped[Devis] = relationship(back_populates="lignes")

    def __repr__(self) -> str:
        return f"<LigneDevis {self.id} devis {self.devis_id}>"
