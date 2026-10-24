"""Agrégat ordre de travail (OT) : l'intervention sur un véhicule et ses tâches prévues.

Statuts (story S3.2) : a_faire → en_cours → termine → livre, une étape à la fois, sans retour.
À l'écran : « En attente », « En cours », « Prêt », « Livré ». `prioritaire` est un drapeau
(badge « Urgent »), pas un statut.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.rendez_vous import RendezVous
    from app.models.utilisateur import Utilisateur
    from app.models.vehicule import Vehicule

# « OT-2026-001 » : trois chiffres au moins, davantage au-delà de 999.
REGEX_NUMERO_OT_SQL = "^OT-[0-9]{4}-[0-9]{3,}$"


class StatutOT(enum.StrEnum):
    A_FAIRE = "a_faire"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    LIVRE = "livre"


ENUM_STATUT_OT = Enum(
    StatutOT,
    name="statut_ot",
    values_callable=lambda statuts: [s.value for s in statuts],
)


class OrdreTravail(TimestampMixin, Base):
    __tablename__ = "ordre_travail"
    __table_args__ = (
        CheckConstraint(f"numero ~ '{REGEX_NUMERO_OT_SQL}'", name="numero_format"),
        CheckConstraint("char_length(btrim(demande_client)) > 0", name="demande_non_vide"),
        CheckConstraint(
            "kilometrage_entree IS NULL OR kilometrage_entree >= 0",
            name="kilometrage_entree_positif",
        ),
        CheckConstraint(
            "cloture_le IS NULL OR cloture_le >= ouvert_le", name="cloture_apres_ouverture"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vehicule_id: Mapped[int] = mapped_column(
        ForeignKey("vehicule.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mecanicien_id: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), index=True
    )
    demande_client: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostic: Mapped[str | None] = mapped_column(Text)
    statut: Mapped[StatutOT] = mapped_column(
        ENUM_STATUT_OT,
        nullable=False,
        default=StatutOT.A_FAIRE,
        server_default=StatutOT.A_FAIRE.value,
        index=True,
    )
    prioritaire: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    kilometrage_entree: Mapped[int | None] = mapped_column(Integer)
    restitution_prevue: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ouvert_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cloture_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cree_par: Mapped[int] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), nullable=False
    )
    # Rendez-vous d'origine (au plus un OT par rendez-vous) : l'OT s'affiche sur son pont.
    rendez_vous_id: Mapped[int | None] = mapped_column(
        ForeignKey("rendez_vous.id", ondelete="RESTRICT"), unique=True
    )

    vehicule: Mapped["Vehicule"] = relationship()
    rendez_vous: Mapped["RendezVous | None"] = relationship(back_populates="ordre")
    mecanicien: Mapped["Utilisateur | None"] = relationship(foreign_keys=[mecanicien_id])
    createur: Mapped["Utilisateur"] = relationship(foreign_keys=[cree_par])
    taches: Mapped[list["TacheOT"]] = relationship(
        back_populates="ordre",
        order_by="(TacheOT.position, TacheOT.id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    historique: Mapped[list["HistoriqueStatut"]] = relationship(
        back_populates="ordre",
        order_by="(HistoriqueStatut.change_le, HistoriqueStatut.id)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def taches_terminees(self) -> int:
        return sum(1 for t in self.taches if t.terminee)

    @property
    def taches_total(self) -> int:
        return len(self.taches)

    def __repr__(self) -> str:
        return f"<OrdreTravail {self.id} {self.numero}>"


class TacheOT(TimestampMixin, Base):
    __tablename__ = "tache_ot"
    __table_args__ = (
        CheckConstraint("char_length(btrim(libelle)) > 0", name="libelle_non_vide"),
        CheckConstraint("duree_prevue_minutes > 0", name="duree_positive"),
        CheckConstraint("position >= 0", name="position_positive"),
        # Une tâche terminée sait quand ; une tâche ouverte n'a ni date ni auteur de fin.
        CheckConstraint(
            "(terminee AND terminee_le IS NOT NULL)"
            " OR (NOT terminee AND terminee_le IS NULL AND terminee_par IS NULL)",
            name="fin_coherente",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ordre_travail_id: Mapped[int] = mapped_column(
        ForeignKey("ordre_travail.id", ondelete="CASCADE"), nullable=False, index=True
    )
    libelle: Mapped[str] = mapped_column(String(200), nullable=False)
    duree_prevue_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    terminee: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    terminee_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminee_par: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT")
    )

    ordre: Mapped[OrdreTravail] = relationship(back_populates="taches")
    terminee_par_utilisateur: Mapped["Utilisateur | None"] = relationship()

    def __repr__(self) -> str:
        return f"<TacheOT {self.id} OT {self.ordre_travail_id}>"


class HistoriqueStatut(Base):
    """Trace d'un changement de statut : qui, quand, de quoi vers quoi (story S3.2).

    Ligne écrite une fois, jamais modifiée : `change_le` tient lieu d'horodatage. La création
    de l'OT est la première ligne (ancien = NULL, nouveau = a_faire).
    """

    __tablename__ = "historique_statut"
    __table_args__ = (CheckConstraint("ancien IS DISTINCT FROM nouveau", name="statut_change"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ordre_travail_id: Mapped[int] = mapped_column(
        ForeignKey("ordre_travail.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ancien: Mapped[StatutOT | None] = mapped_column(ENUM_STATUT_OT)
    nouveau: Mapped[StatutOT] = mapped_column(ENUM_STATUT_OT, nullable=False)
    change_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    utilisateur_id: Mapped[int] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="RESTRICT"), nullable=False
    )

    ordre: Mapped[OrdreTravail] = relationship(back_populates="historique")
    utilisateur: Mapped["Utilisateur"] = relationship()

    def __repr__(self) -> str:
        return f"<HistoriqueStatut OT {self.ordre_travail_id} {self.ancien} → {self.nouveau}>"
