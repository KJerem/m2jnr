"""Paiement d'une facture (story S4.4) : encaissements partiels, cumul plafonné au TTC.

Montant en centimes (> 0). « carte » désigne le terminal de paiement du garage : aucune
donnée de carte n'est saisie ni enregistrée (contrainte du projet).

Garanties de la base (migration 0014) :
- le cumul des paiements d'une facture ne dépasse jamais son TTC : trigger BEFORE INSERT qui
  verrouille la facture (SELECT … FOR UPDATE) puis refuse le dépassement (SQLSTATE ET002) ;
- un paiement ne se modifie ni ne se supprime (SQLSTATE ET003). Corriger un paiement saisi
  par erreur est hors du périmètre du MVP.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.facture import Facture
    from app.models.utilisateur import Utilisateur

SQLSTATE_TROP_PERCU = "ET002"
SQLSTATE_PAIEMENT_IMMUABLE = "ET003"


class ModePaiement(enum.StrEnum):
    CARTE = "carte"
    ESPECES = "especes"
    CHEQUE = "cheque"
    VIREMENT = "virement"


ENUM_MODE_PAIEMENT = Enum(
    ModePaiement,
    name="mode_paiement",
    values_callable=lambda modes: [m.value for m in modes],
)


class Paiement(Base):
    __tablename__ = "paiement"
    __table_args__ = (
        CheckConstraint("montant_centimes > 0", name="montant_positif"),
        CheckConstraint(
            "reference IS NULL OR char_length(btrim(reference)) > 0", name="reference_non_vide"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    facture_id: Mapped[int] = mapped_column(
        ForeignKey("facture.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    montant_centimes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[ModePaiement] = mapped_column(ENUM_MODE_PAIEMENT, nullable=False)
    # Date et heure de réception du règlement (par défaut, l'instant de l'enregistrement).
    recu_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # N° de chèque ou référence du virement, facultatif.
    reference: Mapped[str | None] = mapped_column(String(60))
    cree_par: Mapped[int] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), nullable=False
    )
    cree_le: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    facture: Mapped["Facture"] = relationship(back_populates="paiements")
    createur: Mapped["Utilisateur"] = relationship()

    def __repr__(self) -> str:
        return f"<Paiement {self.id} facture {self.facture_id} {self.montant_centimes}>"
