"""Jeu de données de démonstration (fictif), rejouable sans doublon.

Les mots de passe viennent du fichier .env (DEMO_PASSWORD_GERANT, DEMO_PASSWORD_MECANICIEN) :
aucun secret n'est écrit dans le code.
"""

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.utilisateur import Role
from app.services.utilisateurs import CompteDemo, enregistrer_compte

COMPTE_GERANT = CompteDemo("nadia@garage.test", "Nadia Benali", Role.GERANT)
COMPTES_MECANICIENS = (
    CompteDemo("karim@garage.test", "Karim B.", Role.MECANICIEN),
    CompteDemo("sophie@garage.test", "Sophie M.", Role.MECANICIEN),
    CompteDemo("lucas@garage.test", "Lucas R.", Role.MECANICIEN),
)


class SeedImpossibleError(RuntimeError):
    """Le jeu de démonstration ne peut pas être chargé ; le message est affiché tel quel."""


def semer(db: Session, settings: Settings) -> list[str]:
    """Charge les comptes de démonstration ; renvoie un compte rendu ligne par ligne."""
    if not settings.demo_password_gerant or not settings.demo_password_mecanicien:
        raise SeedImpossibleError(
            "DEMO_PASSWORD_GERANT et DEMO_PASSWORD_MECANICIEN doivent être renseignés dans .env."
        )
    rapport: list[str] = []
    comptes = [(COMPTE_GERANT, settings.demo_password_gerant)] + [
        (compte, settings.demo_password_mecanicien) for compte in COMPTES_MECANICIENS
    ]
    for compte, mot_de_passe in comptes:
        cree = enregistrer_compte(db, compte, mot_de_passe)
        rapport.append(f"{'Créé' if cree else 'À jour'} : {compte.nom} ({compte.email})")
    return rapport
