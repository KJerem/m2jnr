"""Agrégat rendez-vous : un véhicule attendu sur un pont, sur un créneau [début, fin[.

Deux rendez-vous ne se chevauchent jamais sur un même pont : le service le vérifie pour un
message clair, et la contrainte EXCLUDE (btree_gist) le garantit même en cas de requêtes
simultanées. Les créneaux sont semi-ouverts '[)' : 9 h 00 – 10 h 30 puis 10 h 30 – 11 h 00
sont compatibles.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    literal_column,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ordre_travail import OrdreTravail
    from app.models.pont import Pont
    from app.models.utilisateur import Utilisateur
    from app.models.vehicule import Vehicule

DUREE_MAX_MINUTES = 600
NOM_CONTRAINTE_CRENEAU = "excl_rendez_vous_pont_creneau"

# Fin calculée par la base. « timestamptz + interval » n'est pas IMMUTABLE (il dépend du
# fuseau de la session), ce qu'exige une colonne générée : le calcul passe par l'heure UTC
# sans fuseau, pour laquelle l'addition de minutes est immuable (et juste aux changements
# d'heure).
EXPRESSION_FIN = (
    "((debut AT TIME ZONE 'UTC') + duree_minutes * interval '1 minute') AT TIME ZONE 'UTC'"
)


class RendezVous(TimestampMixin, Base):
    __tablename__ = "rendez_vous"
    __table_args__ = (
        CheckConstraint(
            f"duree_minutes > 0 AND duree_minutes <= {DUREE_MAX_MINUTES}", name="duree_bornee"
        ),
        CheckConstraint("char_length(btrim(motif)) > 0", name="motif_non_vide"),
        ExcludeConstraint(
            ("pont_id", "="),
            (literal_column("tstzrange(debut, fin, '[)')"), "&&"),
            name=NOM_CONTRAINTE_CRENEAU,
            using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicule_id: Mapped[int] = mapped_column(
        ForeignKey("vehicule.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    pont_id: Mapped[int] = mapped_column(
        ForeignKey("pont.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    debut: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duree_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    fin: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), Computed(EXPRESSION_FIN, persisted=True)
    )
    motif: Mapped[str] = mapped_column(Text, nullable=False)
    cree_par: Mapped[int] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), nullable=False
    )

    vehicule: Mapped["Vehicule"] = relationship()
    pont: Mapped["Pont"] = relationship()
    createur: Mapped["Utilisateur"] = relationship()
    ordre: Mapped["OrdreTravail | None"] = relationship(back_populates="rendez_vous")

    def __repr__(self) -> str:
        return f"<RendezVous {self.id} pont {self.pont_id}>"
