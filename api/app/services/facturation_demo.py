"""Devis et factures de démonstration (story S4.3), sur les OT de la journée de démo.

- devis de la Peugeot du jour : exactement les lignes de la maquette (454,80 € TTC), non
  facturé (l'intervention est en cours) ;
- devis de la Toyota « Prêt », non facturé : il apparaît dans « Facture à établir » ;
- devis et factures des OT livrés, dans l'ordre chronologique : Peugeot de l'an dernier
  (F-AAAA-001 de l'an dernier), Peugeot d'avril (F-AAAA-001), BMW livrée aujourd'hui
  (F-AAAA-002), pour que « Facturé aujourd'hui » ne soit pas nul.

Rejouable : un devis existant n'est jamais modifié, une facture n'est jamais recréée ni
modifiée (la base l'interdit de toute façon) ; on vérifie leur existence avant de créer.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.devis import Devis
from app.models.ordre_travail import OrdreTravail, StatutOT
from app.models.utilisateur import Utilisateur
from app.models.vehicule import Vehicule
from app.schemas.devis import LigneEntree
from app.services import devis as service_devis
from app.services import factures as service_factures
from app.services.format import formater_euros
from app.services.journee_demo import GERANT


@dataclass(frozen=True)
class LigneDemo:
    type: str
    reference: str
    designation: str
    quantite: str
    prix_centimes: int


@dataclass(frozen=True)
class DevisDemo:
    plaque: str
    demande: str
    lignes: tuple[LigneDemo, ...]


def _mo(reference: str, designation: str, heures: str, prix: int = 7200) -> LigneDemo:
    return LigneDemo("main_oeuvre", reference, designation, heures, prix)


def _piece(reference: str, designation: str, prix: int, quantite: str = "1") -> LigneDemo:
    return LigneDemo("piece", reference, designation, quantite, prix)


DEVIS_DEMO: tuple[DevisDemo, ...] = (
    DevisDemo(
        "GH-482-KL",
        "Révision des 75 000 km.",
        (
            _mo("MO-REVISION", "Révision des 75 000 km", "1", 6800),
            _piece("FLT-AIR-308", "Filtre à air", 2150),
            _piece("HUI-5W30-5L", "Huile moteur 5W30, bidon 5 L", 4190),
            _piece("FLT-H-12PT", "Filtre à huile 1.2 PureTech", 1120),
        ),
    ),
    DevisDemo(
        "GH-482-KL",
        "Remplacement des pneus avant.",
        (
            _mo("MO-PNEUS", "Montage et équilibrage de deux pneus", "0.75", 7000),
            _piece("PNEU-225-45R17", "Pneu 225/45 R17 91W", 9800, "2"),
        ),
    ),
    DevisDemo(
        "FS-341-RD",
        "Vidange et contrôle avant un long trajet.",
        (
            _mo("MO-VIDANGE", "Vidange + filtre", "0.5"),
            _mo("MO-CONTROLE", "Contrôle des freins et des pneus", "0.5"),
            _piece("HUI-5W30-5L", "Huile moteur 5W30, bidon 5 L", 4290),
            _piece("FLT-H-B38", "Filtre à huile 1.5 B38", 1420),
        ),
    ),
    # Maquette « détail d'un OR » : 180,00 + 199,00 = 379,00 € HT, 454,80 € TTC.
    DevisDemo(
        "GH-482-KL",
        "Bruit au freinage côté avant gauche, surtout à basse vitesse.",
        (
            _mo("MO-DIAG", "Diagnostic freinage", "0.5"),
            _mo("MO-FREIN-AV", "Remplacement plaquettes + disques AV", "1.5"),
            _mo("MO-VIDANGE", "Vidange + filtre", "0.5"),
            _piece("PLQ-308-AV", "Jeu de plaquettes avant", 4850),
            _piece("DSQ-308-283", "Disques avant ventilés (paire)", 9600),
            _piece("HUI-5W30-5L", "Huile moteur 5W30, bidon 5 L", 4290),
            _piece("FLT-H-12PT", "Filtre à huile 1.2 PureTech", 1160),
        ),
    ),
    DevisDemo(
        "HB-205-MZ",
        "Démarrage difficile le matin, révision annuelle.",
        (
            _mo("MO-BATTERIE", "Test et remplacement de la batterie", "0.75"),
            _mo("MO-REVISION", "Révision annuelle", "0.75"),
            _piece("BAT-12V-60AH", "Batterie 12 V 60 Ah", 12900),
            _piece("HUI-0W20-4L", "Huile moteur 0W20, bidon 4 L", 3850),
            _piece("FLT-H-YARIS", "Filtre à huile", 980),
        ),
    ),
)


def _ordre(db: Session, demo: DevisDemo) -> OrdreTravail | None:
    return db.scalars(
        select(OrdreTravail)
        .join(OrdreTravail.vehicule)
        .where(Vehicule.immatriculation == demo.plaque, OrdreTravail.demande_client == demo.demande)
    ).first()


def _lignes(demo: DevisDemo) -> list[LigneEntree]:
    return [
        LigneEntree.model_validate(
            {
                "type": ligne.type,
                "reference": ligne.reference,
                "designation": ligne.designation,
                "quantite": ligne.quantite,
                "prix_unitaire_ht_centimes": ligne.prix_centimes,
            }
        )
        for ligne in demo.lignes
    ]


def semer_facturation(db: Session, maintenant: datetime, settings: Settings) -> list[str]:
    """Crée les devis puis les factures de démonstration manquants ; renvoie un compte rendu."""
    gerant = db.scalars(select(Utilisateur).where(Utilisateur.email == GERANT)).one()
    rapport: list[str] = []
    a_facturer: list[tuple[OrdreTravail, Devis]] = []
    for demo in DEVIS_DEMO:
        ordre = _ordre(db, demo)
        if ordre is None:
            continue
        devis = service_devis.devis_courant(db, ordre.id)
        cree = devis is None
        if devis is None:
            # Chiffré peu après l'ouverture, jamais dans le futur ni après la livraison.
            moment = min(ordre.ouvert_le + timedelta(minutes=40), ordre.cloture_le or maintenant)
            devis = service_devis.creer_devis(
                db, ordre, _lignes(demo), gerant, min(moment, maintenant)
            )
        rapport.append(
            f"{'Créé' if cree else 'À jour'} : devis {ordre.numero}"
            f" ({formater_euros(devis.total_ttc_centimes)} TTC)"
        )
        if ordre.statut == StatutOT.LIVRE and ordre.cloture_le is not None:
            a_facturer.append((ordre, devis))

    # Factures dans l'ordre des livraisons : numéros chronologiques par année de Paris.
    for ordre, devis in sorted(a_facturer, key=lambda paire: paire[0].cloture_le or maintenant):
        facture = service_factures.facture_du_devis(db, devis.id)
        cree = facture is None
        if facture is None:
            emission = min(ordre.cloture_le or maintenant, maintenant)
            facture = service_factures.etablir_facture(db, devis, gerant, emission, settings)
        rapport.append(
            f"{'Créé' if cree else 'À jour'} : facture {facture.numero} {ordre.numero}"
            f" ({formater_euros(facture.total_ttc_centimes)} TTC)"
        )
    return rapport
