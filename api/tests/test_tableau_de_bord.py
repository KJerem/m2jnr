"""Tableau de bord du gérant : indicateurs et listes du jour de Paris, horloge contrôlée."""

from collections.abc import Callable
from datetime import UTC, datetime
from itertools import count
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Client,
    Devis,
    OrdreTravail,
    Pont,
    RendezVous,
    Role,
    StatutDevis,
    StatutOT,
    Utilisateur,
    Vehicule,
)
from app.schemas.devis import DevisEntree
from app.services import devis as service_devis
from app.services import factures as service_factures
from app.services.statut_devis import changer_statut_devis
from app.services.tableau_de_bord import formater_retard, variation_pct
from tests.conftest import Horloge, MakeUser
from tests.test_s4_1_devis import LIGNES_BACKLOG

NBSP = " "
# Horloge des tests : lundi 2 novembre 2026, 14 h 47 à Paris (13 h 47 UTC).
PLAQUES = iter(f"AA-{n:03d}-AA" for n in count(101))


def utc(jour: int, heure: int, minute: int = 0, mois: int = 11) -> datetime:
    return datetime(2026, mois, jour, heure, minute, tzinfo=UTC)


@pytest.fixture
def fabrique(db: Session, gerant: Utilisateur, make_user: MakeUser) -> Callable[..., OrdreTravail]:
    numeros = count(1)
    karim = make_user(Role.MECANICIEN, nom="Karim B.")

    def _ordre(
        *,
        statut: StatutOT = StatutOT.EN_COURS,
        ouvert: datetime = utc(2, 7, 10),
        restitution: datetime | None = None,
        cloture: datetime | None = None,
        prioritaire: bool = False,
        mecanicien: bool = True,
        client: tuple[str, str] = ("Laurent", "Claire"),
        modele: tuple[str, str] = ("Peugeot", "308 SW"),
    ) -> OrdreTravail:
        proprietaire = Client(nom=client[0], prenom=client[1], telephone="0612483075")
        db.add(proprietaire)
        db.flush()
        vehicule = Vehicule(
            client_id=proprietaire.id,
            immatriculation=next(PLAQUES),
            marque=modele[0],
            modele=modele[1],
            kilometrage=10_000,
        )
        ordre = OrdreTravail(
            numero=f"OT-2026-{next(numeros):03d}",
            vehicule=vehicule,
            demande_client="Contrôle.",
            statut=statut,
            prioritaire=prioritaire,
            restitution_prevue=restitution,
            ouvert_le=ouvert,
            cloture_le=cloture,
            mecanicien=karim if mecanicien else None,
            createur=gerant,
        )
        db.add_all([vehicule, ordre])
        db.flush()
        return ordre

    return _ordre


def _accepte(devis: Devis, gerant: Utilisateur) -> Devis:
    """Envoyé puis accepté à la date de sa création (seul un devis accepté se facture)."""
    changer_statut_devis(devis, StatutDevis.ENVOYE, gerant, devis.cree_le)
    changer_statut_devis(devis, StatutDevis.ACCEPTE, gerant, devis.cree_le)
    return devis


def _facturer(
    db: Session, ordre: OrdreTravail, gerant: Utilisateur, emise: datetime, lignes: Any = None
) -> int:
    entree = DevisEntree.model_validate({"lignes": lignes or LIGNES_BACKLOG})
    devis = _accepte(service_devis.creer_devis(db, ordre, entree.lignes, gerant, emise), gerant)
    facture = service_factures.etablir_facture(db, devis, gerant, emise, get_settings())
    return facture.total_ttc_centimes


def _rendez_vous(db: Session, ordre: OrdreTravail, debut: datetime, motif: str) -> None:
    pont = db.query(Pont).filter_by(nom="Pont 1").one()
    db.add(
        RendezVous(
            vehicule=ordre.vehicule,
            pont=pont,
            debut=debut,
            duree_minutes=30,
            motif=motif,
            createur=ordre.createur,
        )
    )
    db.flush()


def test_indicateurs_et_listes_de_la_journee(
    horloge: Horloge,
    client_gerant: TestClient,
    db: Session,
    gerant: Utilisateur,
    fabrique: Callable[..., OrdreTravail],
) -> None:
    # Promise à 12 h 00 (Paris), il est 14 h 47 : en retard de 2 h 47.
    dacia = fabrique(
        ouvert=utc(2, 7, 25),
        restitution=utc(2, 11),
        client=("Kone", "Aminata"),
        modele=("Dacia", "Sandero"),
    )
    pret = fabrique(statut=StatutOT.TERMINE, restitution=utc(2, 15), ouvert=utc(2, 8, 25))
    pret_demain = fabrique(statut=StatutOT.TERMINE, restitution=utc(3, 15), ouvert=utc(2, 9))
    sans_mecanicien = fabrique(
        statut=StatutOT.A_FAIRE, ouvert=utc(1, 9), mecanicien=False, modele=("Citroën", "C3")
    )
    livre_du_jour = fabrique(statut=StatutOT.LIVRE, ouvert=utc(2, 6, 35), cloture=utc(2, 9, 15))
    livre_hier = fabrique(statut=StatutOT.LIVRE, ouvert=utc(1, 7), cloture=utc(1, 16))
    entree = DevisEntree.model_validate({"lignes": LIGNES_BACKLOG})
    # Devis accepté, non facturé : facture à établir.
    _accepte(service_devis.creer_devis(db, pret, entree.lignes, gerant, utc(2, 9)), gerant)
    assert _facturer(db, livre_du_jour, gerant, utc(2, 9, 20)) == 16_800
    # Lundi précédent (26 octobre, heure d'hiver) : 150,00 € TTC facturés.
    lignes_150 = [{"type": "piece", "designation": "Pièce", "quantite": "1",
                   "prix_unitaire_ht_centimes": 12_500}]  # fmt: skip
    assert _facturer(db, livre_hier, gerant, utc(26, 10, mois=10), lignes_150) == 15_000
    _rendez_vous(db, dacia, utc(2, 8), "Révision passée")
    _rendez_vous(db, pret, utc(2, 14), "Révision 60 000 km")
    _rendez_vous(db, pret_demain, utc(2, 16, 45), "Pneus hiver")
    _rendez_vous(db, sans_mecanicien, utc(3, 8), "Demain")

    reponse = client_gerant.get("/tableau-de-bord")

    assert reponse.status_code == 200
    donnees = reponse.json()
    assert donnees["jour"] == "2026-11-02"
    assert (donnees["ponts_actifs"], donnees["mecaniciens_actifs"]) == (3, 1)
    assert donnees["kpis"] == {
        "vehicules_atelier": 4,
        "entres_aujourdhui": 4,  # dacia, prêt, prêt demain et livré du jour
        "prets_a_restituer": 2,
        "a_restituer_aujourdhui": 1,
        "en_retard": 1,
        "rendez_vous_aujourdhui": 3,
        "prochain_rendez_vous": "2026-11-02T14:00:00Z",
        "facture_aujourdhui_ttc_centimes": 16_800,
        "facture_semaine_derniere_ttc_centimes": 15_000,
        "jour_comparaison": "2026-10-26",
        "variation_pct": 12,
    }
    # Urgentes ou en retard d'abord, puis par restitution, sans heure ensuite, livrés à la fin.
    assert [o["id"] for o in donnees["interventions"]] == [
        dacia.id,
        pret.id,
        pret_demain.id,
        sans_mecanicien.id,
        livre_du_jour.id,
    ]
    assert donnees["interventions"][0]["en_retard"] is True
    assert [(a["heure"], a["motif"]) for a in donnees["arrivees"]] == [
        ("2026-11-02T14:00:00Z", "Révision 60 000 km"),
        ("2026-11-02T16:45:00Z", "Pneus hiver"),
    ]
    assert donnees["a_traiter"] == [
        {
            "type": "retard",
            "titre": "Aminata Kone attend",
            "detail": (
                f"Dacia Sandero · {dacia.numero} · promis à 12{NBSP}h{NBSP}00,"
                f" retard de 2{NBSP}h{NBSP}47"
            ),
            "ordre_id": dacia.id,
            "numero": dacia.numero,
        },
        {
            "type": "facture_a_etablir",
            "titre": "Facture à établir",
            "detail": f"Claire Laurent · Peugeot 308 SW · {pret.numero} · 168,00{NBSP}€ TTC",
            "ordre_id": pret.id,
            "numero": pret.numero,
        },
        {
            "type": "non_affecte",
            "titre": "Mécanicien à affecter",
            "detail": f"Citroën C3 · {sans_mecanicien.numero} · Claire Laurent",
            "ordre_id": sans_mecanicien.id,
            "numero": sans_mecanicien.numero,
        },
    ]


def test_retard_detecte_strictement_apres_l_heure_promise(
    horloge: Horloge, client_gerant: TestClient, fabrique: Callable[..., OrdreTravail]
) -> None:
    a_l_heure = fabrique(restitution=horloge.maintenant)
    pret_en_retard = fabrique(statut=StatutOT.TERMINE, restitution=utc(2, 9))
    hier = fabrique(restitution=utc(1, 16, 30), ouvert=utc(1, 7))

    donnees = client_gerant.get("/tableau-de-bord").json()

    assert donnees["kpis"]["en_retard"] == 1
    retards = [a for a in donnees["a_traiter"] if a["type"] == "retard"]
    assert [a["ordre_id"] for a in retards] == [hier.id]
    # Promise la veille à 17 h 30 (Paris) : le jour est précisé, retard de plus d'une journée.
    assert retards[0]["detail"].endswith(
        f"promis le dim. 1 nov. à 17{NBSP}h{NBSP}30, retard de 21{NBSP}h{NBSP}17"
    )
    ids = {o["id"]: o["en_retard"] for o in donnees["interventions"]}
    assert ids[a_l_heure.id] is False
    assert ids[pret_en_retard.id] is False  # un véhicule prêt n'est plus en retard


def test_bornes_du_jour_a_l_heure_de_paris(
    horloge: Horloge,
    client_gerant: TestClient,
    db: Session,
    gerant: Utilisateur,
    fabrique: Callable[..., OrdreTravail],
) -> None:
    # Dimanche 1er novembre à 23 h 30 (Paris) = 22 h 30 UTC : la veille.
    veille = fabrique(statut=StatutOT.LIVRE, ouvert=utc(1, 20), cloture=utc(1, 22, 30))
    _facturer(db, veille, gerant, utc(1, 22, 30))
    # Lundi 2 novembre à 0 h 10 (Paris) = dimanche 23 h 10 UTC : aujourd'hui.
    minuit = fabrique(statut=StatutOT.LIVRE, ouvert=utc(1, 23, 5), cloture=utc(1, 23, 10))
    _facturer(db, minuit, gerant, utc(1, 23, 10))

    donnees = client_gerant.get("/tableau-de-bord").json()

    assert donnees["kpis"]["facture_aujourdhui_ttc_centimes"] == 16_800
    assert donnees["kpis"]["entres_aujourdhui"] == 1
    assert [o["id"] for o in donnees["interventions"]] == [minuit.id]


def test_variation_nulle_quand_rien_n_etait_facture_la_semaine_derniere(
    horloge: Horloge,
    client_gerant: TestClient,
    db: Session,
    gerant: Utilisateur,
    fabrique: Callable[..., OrdreTravail],
) -> None:
    livre = fabrique(statut=StatutOT.LIVRE, cloture=utc(2, 9))
    _facturer(db, livre, gerant, utc(2, 9, 5))

    kpis = client_gerant.get("/tableau-de-bord").json()["kpis"]

    assert kpis["facture_aujourdhui_ttc_centimes"] == 16_800
    assert kpis["facture_semaine_derniere_ttc_centimes"] == 0
    assert kpis["variation_pct"] is None


def test_journee_vide(horloge: Horloge, client_gerant: TestClient) -> None:
    donnees = client_gerant.get("/tableau-de-bord").json()

    assert donnees["interventions"] == donnees["arrivees"] == donnees["a_traiter"] == []
    assert donnees["kpis"]["prochain_rendez_vous"] is None
    assert donnees["kpis"]["facture_aujourdhui_ttc_centimes"] == 0


@pytest.mark.parametrize(
    ("aujourdhui", "reference", "attendu"),
    [
        (16_800, 15_000, 12),
        (0, 15_000, -100),
        (1_005, 1_000, 1),  # + 0,5 % → 1 %
        (995, 1_000, -1),  # − 0,5 % → − 1 % (demi arrondi en s'éloignant de zéro)
        (1_000, 1_000, 0),
        (500, 0, None),
        (0, 0, None),
    ],
)
def test_variation_en_pour_cent(aujourdhui: int, reference: int, attendu: int | None) -> None:
    assert variation_pct(aujourdhui, reference) == attendu


@pytest.mark.parametrize(
    ("minutes", "attendu"),
    [
        (40, f"40{NBSP}min"),
        (160, f"2{NBSP}h{NBSP}40"),
        (180, f"3{NBSP}h"),
        (1_500, f"1{NBSP}j 1{NBSP}h"),
    ],
)
def test_format_du_retard(minutes: int, attendu: str) -> None:
    assert formater_retard(minutes) == attendu


def test_mecanicien_refuse_et_sans_session_401(
    client_mecanicien: TestClient, client_anonyme: TestClient
) -> None:
    reponse = client_mecanicien.get("/tableau-de-bord")

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "interdit"
    assert client_anonyme.get("/tableau-de-bord").status_code == 401
