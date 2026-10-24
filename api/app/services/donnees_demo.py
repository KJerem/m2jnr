"""Jeu de données de démonstration (fictif), rejouable sans doublon.

Les mots de passe viennent du fichier .env (DEMO_PASSWORD_GERANT, DEMO_PASSWORD_MECANICIEN) :
aucun secret n'est écrit dans le code. Les clients et véhicules reprennent ceux des maquettes ;
téléphones et e-mails sont inventés (domaine réservé exemple.test). La journée d'atelier
(ordres de travail, rendez-vous, historique) est décrite dans journee_demo.py, ses devis et
factures dans facturation_demo.py.
"""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import get_now
from app.config import Settings
from app.models.client import Client
from app.models.utilisateur import Role
from app.models.vehicule import Vehicule
from app.schemas.client import ClientEntree
from app.schemas.vehicule import VehiculeEntree
from app.services.facturation_demo import semer_facturation
from app.services.journee_demo import semer_journee
from app.services.utilisateurs import CompteDemo, enregistrer_compte

COMPTE_GERANT = CompteDemo("nadia@garage.test", "Nadia Benali", Role.GERANT)
COMPTES_MECANICIENS = (
    CompteDemo("karim@garage.test", "Karim B.", Role.MECANICIEN),
    CompteDemo("sophie@garage.test", "Sophie M.", Role.MECANICIEN),
    CompteDemo("lucas@garage.test", "Lucas R.", Role.MECANICIEN),
)


@dataclass(frozen=True)
class FicheDemo:
    client: ClientEntree
    vehicule: VehiculeEntree


def _fiche(
    nom: str,
    prenom: str,
    telephone: str,
    consentement: bool,
    immatriculation: str,
    marque: str,
    modele: str,
    kilometrage: int,
    mise_en_circulation: date | None,
    vin: str | None = None,
) -> FicheDemo:
    email = f"{prenom}.{nom}".lower().replace(" ", "-") + "@exemple.test"
    return FicheDemo(
        client=ClientEntree(
            nom=nom,
            prenom=prenom,
            telephone=telephone,
            email=email,
            consentement_rappels=consentement,
        ),
        vehicule=VehiculeEntree(
            immatriculation=immatriculation,
            marque=marque,
            modele=modele,
            kilometrage=kilometrage,
            vin=vin,
            date_mise_en_circulation=mise_en_circulation,
        ),
    )


FICHES_DEMO: tuple[FicheDemo, ...] = (
    _fiche(
        "Laurent", "Claire", "06 12 48 30 75", True,
        "GH-482-KL", "Peugeot", "308 SW", 84_312, date(2019, 3, 1), vin="VF3LCYHZPKS123456",
    ),
    _fiche("Petit", "Thomas", "06 23 59 41 86", False,
           "EK-730-PA", "Volkswagen", "Golf 7", 112_450, date(2017, 6, 12)),
    _fiche("Kone", "Aminata", "06 34 60 52 97", True,
           "GA-664-SN", "Dacia", "Sandero", 45_210, date(2021, 9, 3)),
    _fiche("Diallo", "Moussa", "06 45 71 63 08", False,
           "FD-119-RT", "Renault", "Clio V", 38_900, date(2019, 11, 20)),
    _fiche("Moreau", "Julien", "06 56 82 74 19", True,
           "CZ-918-LE", "Citroën", "C3", 97_340, date(2013, 4, 8)),
    _fiche("Roux", "Isabelle", "06 67 93 85 20", False,
           "DL-552-VK", "Renault", "Megane IV", 76_120, None),
    _fiche("Nguyen", "Linh", "06 78 04 96 31", True,
           "HB-205-MZ", "Toyota", "Yaris", 15_800, date(2021, 12, 2)),
    _fiche("Garcia", "Antoine", "06 89 15 07 42", False,
           "FS-341-RD", "BMW", "Série 1", 52_600, date(2019, 8, 27)),
)  # fmt: skip


class SeedImpossibleError(RuntimeError):
    """Le jeu de démonstration ne peut pas être chargé ; le message est affiché tel quel."""


def _copier_client(client: Client, donnees: ClientEntree) -> None:
    client.nom = donnees.nom
    client.prenom = donnees.prenom
    client.telephone = donnees.telephone
    client.email = donnees.email
    client.consentement_rappels = donnees.consentement_rappels


def _copier_vehicule(vehicule: Vehicule, donnees: VehiculeEntree) -> None:
    vehicule.immatriculation = donnees.immatriculation
    vehicule.marque = donnees.marque
    vehicule.modele = donnees.modele
    vehicule.kilometrage = donnees.kilometrage
    vehicule.vin = donnees.vin
    vehicule.date_mise_en_circulation = donnees.date_mise_en_circulation


def enregistrer_fiche(db: Session, fiche: FicheDemo) -> bool:
    """Crée ou remet à jour un client de démonstration et son véhicule (clé : la plaque).

    Renvoie True si le véhicule a été créé.
    """
    vehicule = db.scalar(
        select(Vehicule).where(Vehicule.immatriculation == fiche.vehicule.immatriculation)
    )
    if vehicule is not None:
        _copier_client(vehicule.client, fiche.client)
        _copier_vehicule(vehicule, fiche.vehicule)
        db.flush()
        return False
    client = db.scalar(
        select(Client)
        .where(Client.telephone == fiche.client.telephone, Client.nom == fiche.client.nom)
        .order_by(Client.id)
    )
    if client is None:
        client = Client()
        db.add(client)
    _copier_client(client, fiche.client)
    db.flush()
    vehicule = Vehicule(client_id=client.id)
    _copier_vehicule(vehicule, fiche.vehicule)
    db.add(vehicule)
    db.flush()
    return True


def semer(db: Session, settings: Settings, maintenant: datetime | None = None) -> list[str]:
    """Charge les comptes, clients, véhicules, la journée d'atelier, ses devis et ses factures
    de démonstration (datés par rapport à `maintenant`, l'heure courante par défaut) ; renvoie
    un compte rendu."""
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
    for fiche in FICHES_DEMO:
        cree = enregistrer_fiche(db, fiche)
        v, c = fiche.vehicule, fiche.client
        rapport.append(
            f"{'Créé' if cree else 'À jour'} : {v.marque} {v.modele} {v.immatriculation}"
            f" ({c.prenom} {c.nom})"
        )
    instant = maintenant or get_now()
    rapport += semer_journee(db, instant, settings.timezone)
    rapport += semer_facturation(db, instant, settings)
    return rapport
