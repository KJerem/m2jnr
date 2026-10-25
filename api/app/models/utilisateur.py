"""Agrégat utilisateur : employé du garage (gérant ou mécanicien)."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Role(enum.StrEnum):
    GERANT = "gerant"
    MECANICIEN = "mecanicien"


class StatutCompte(enum.StrEnum):
    """Statut du compte (story S8.2) : seul un compte actif ouvre une session.

    « en_attente » : inscription pas encore validée par un gérant (story S8.3) ;
    « desactive » : ancien employé ou compte suspendu par un gérant."""

    ACTIF = "actif"
    EN_ATTENTE = "en_attente"
    DESACTIVE = "desactive"


class Utilisateur(TimestampMixin, Base):
    __tablename__ = "utilisateur"
    __table_args__ = (CheckConstraint("tentatives_echouees >= 0", name="tentatives_positives"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    # Peut être vide pour un compte repris d'avant le sprint 5 dont le nom n'avait qu'un mot.
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
    statut: Mapped[StatutCompte] = mapped_column(
        Enum(
            StatutCompte,
            name="statut_compte",
            values_callable=lambda statuts: [s.value for s in statuts],
        ),
        nullable=False,
        default=StatutCompte.ACTIF,
        server_default=text("'actif'"),
    )
    tentatives_echouees: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    bloque_jusqu_a: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valide_par: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="SET NULL")
    )
    desactive_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    desactive_par: Mapped[int | None] = mapped_column(
        ForeignKey("utilisateur.id", ondelete="SET NULL")
    )
    # Une session émise avant cette date est refusée (désactivation, nouveau mot de passe).
    sessions_valides_depuis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def actif(self) -> bool:
        """Vrai si le compte peut se connecter (statut « actif »)."""
        return self.statut == StatutCompte.ACTIF

    def session_valide(self, emise_le: datetime) -> bool:
        """Vrai si une session émise à `emise_le` vaut encore pour ce compte : il est actif et
        aucune désactivation ni réinitialisation du mot de passe n'a eu lieu depuis. La
        comparaison se fait à la seconde, la précision du jeton (`iat`)."""
        if not self.actif:
            return False
        depuis = self.sessions_valides_depuis
        return depuis is None or int(emise_le.timestamp()) >= int(depuis.timestamp())

    @property
    def nom_affiche(self) -> str:
        """Prénom puis nom, tels que saisis : « Nadia Benali », « Karim B. »."""
        return " ".join(part for part in (self.prenom, self.nom) if part)

    def __repr__(self) -> str:
        return f"<Utilisateur {self.id} {self.role.value}>"
