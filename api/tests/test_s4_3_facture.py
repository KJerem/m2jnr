"""Story S4.3 — facture : numéro sans trou, copie figée du devis, immuabilité, PDF, accès."""

import importlib.util
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import Engine, delete, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import (
    Client,
    Compteur,
    Devis,
    Facture,
    LigneFacture,
    OrdreTravail,
    Role,
    StatutDevis,
    StatutOT,
    Utilisateur,
    Vehicule,
)
from app.routers import factures as routes_factures
from app.schemas.devis import DevisEntree
from app.services import devis as service_devis
from app.services.numerotation import prochain_numero
from app.services.statut_devis import changer_statut_devis
from tests.conftest import Horloge, connecter
from tests.test_concurrence_ordres import en_parallele, nouvelle_session
from tests.test_s4_1_devis import LIGNES_BACKLOG, LIGNES_MAQUETTE


def _ordre(db: Session, gerant: Utilisateur, statut: StatutOT = StatutOT.TERMINE) -> OrdreTravail:
    vehicule = db.scalars(select(Vehicule).where(Vehicule.immatriculation == "GH-482-KL")).first()
    if vehicule is None:
        client = Client(
            nom="Laurent", prenom="Claire", telephone="0612483075", email="claire@exemple.test"
        )
        db.add(client)
        db.flush()
        vehicule = Vehicule(
            client_id=client.id,
            immatriculation="GH-482-KL",
            marque="Peugeot",
            modele="308 SW",
            kilometrage=84_312,
        )
        db.add(vehicule)
        db.flush()
    rang = db.scalar(select(OrdreTravail.id).order_by(OrdreTravail.id.desc()).limit(1)) or 0
    numero = f"OT-2026-{rang + 1:03d}"
    ordre = OrdreTravail(
        numero=numero,
        vehicule=vehicule,
        demande_client="Bruit au freinage côté avant gauche.",
        statut=statut,
        kilometrage_entree=84_312,
        ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
        createur=gerant,
    )
    db.add(ordre)
    db.flush()
    return ordre


@pytest.fixture
def nouvel_ordre(db: Session, gerant: Utilisateur) -> Callable[..., OrdreTravail]:
    def _nouveau(statut: StatutOT = StatutOT.TERMINE) -> OrdreTravail:
        return _ordre(db, gerant, statut)

    return _nouveau


def _devis(c: TestClient, ordre: OrdreTravail, lignes: list[dict[str, Any]]) -> dict[str, Any]:
    """Devis créé puis accepté par le client (story S4.2 : seul un devis accepté se facture)."""
    reponse = c.post(f"/ordres/{ordre.id}/devis", json={"lignes": lignes})
    assert reponse.status_code == 201, reponse.text
    for nouveau in ("envoye", "accepte"):
        statut = c.post(f"/devis/{reponse.json()['id']}/statut", json={"nouveau": nouveau})
        assert statut.status_code == 200, statut.text
    return dict(statut.json())


def _facturer(c: TestClient, devis_id: int) -> dict[str, Any]:
    reponse = c.post(f"/devis/{devis_id}/facture")
    assert reponse.status_code == 201, reponse.text
    return dict(reponse.json())


# --- Émission --------------------------------------------------------------------------------


def test_facture_168_euros_identique_au_devis(
    horloge: Horloge,
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    ordre = nouvel_ordre()
    devis = _devis(client_gerant, ordre, LIGNES_BACKLOG)

    facture = _facturer(client_gerant, devis["id"])

    assert facture["numero"] == "F-2026-001"
    assert facture["totaux"] == devis["totaux"]
    assert facture["totaux"]["total_ttc_centimes"] == 16_800
    assert facture["emise_le"] == "2026-11-02T13:47:00Z"
    assert facture["echeance"] == "2026-12-02"  # 30 jours après le 2 novembre (Paris)
    assert facture["devis_id"] == devis["id"]
    assert facture["ordre"] == {"id": ordre.id, "numero": ordre.numero}
    assert facture["client"] == {
        "nom": "Laurent",
        "prenom": "Claire",
        "telephone": "0612483075",
        "email": "claire@exemple.test",
    }
    assert facture["vehicule"] == {
        "immatriculation": "GH-482-KL",
        "marque": "Peugeot",
        "modele": "308 SW",
        "kilometrage": 84_312,
    }
    reglages = get_settings()
    assert facture["garage"]["siret"] == reglages.garage_siret
    assert facture["garage"]["tva_intracommunautaire"] == reglages.garage_tva_intra
    assert [
        (ligne["designation"], ligne["quantite"], ligne["total_ht_centimes"])
        for ligne in facture["lignes"]
    ] == [
        (ligne["designation"], ligne["quantite"], ligne["total_ht_centimes"])
        for ligne in devis["lignes"]
    ]
    assert client_gerant.get(f"/factures/{facture['id']}").json() == facture
    lien = {"id": facture["id"], "numero": "F-2026-001"}
    assert client_gerant.get(f"/devis/{devis['id']}").json()["facture"] == lien
    assert client_gerant.get(f"/ordres/{ordre.id}/devis").json()["facture"] == lien
    assert client_gerant.get(f"/ordres/{ordre.id}").json()["facture"] == lien
    # Le mécanicien ne reçoit ni la facture ni aucun montant sur la fiche de l'OT.
    fiche = client_mecanicien.get(f"/ordres/{ordre.id}")
    assert fiche.json()["facture"] is None
    assert "centimes" not in fiche.text


def test_facture_de_la_maquette_454_80_euros(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(StatutOT.LIVRE), LIGNES_MAQUETTE)

    facture = _facturer(client_gerant, devis["id"])

    assert facture["totaux"] == {
        "main_oeuvre_ht_centimes": 18_000,
        "pieces_ht_centimes": 19_900,
        "total_ht_centimes": 37_900,
        "total_tva_centimes": 7_580,
        "total_ttc_centimes": 45_480,
    }
    assert facture["taux_tva_bp"] == 2000
    assert len(facture["lignes"]) == 7


def test_numeros_consecutifs(
    horloge: Horloge, client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    numeros = []
    for _ in range(3):
        devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
        numeros.append(_facturer(client_gerant, devis["id"])["numero"])

    assert numeros == ["F-2026-001", "F-2026-002", "F-2026-003"]


def test_changement_d_annee_a_l_heure_de_paris(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    devis = [_devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG) for _ in range(3)]
    # 31 décembre 2026 à 23 h 30 à Paris : encore 2026, échéance au 30 janvier.
    horloge.maintenant = datetime(2026, 12, 31, 22, 30, tzinfo=UTC)
    connecter(client_gerant, gerant.email)
    premiere = _facturer(client_gerant, devis[0]["id"])
    assert (premiere["numero"], premiere["echeance"]) == ("F-2026-001", "2027-01-30")
    # 1er janvier 2027 à 0 h 30 à Paris (23 h 30 UTC la veille) : la série repart à 001.
    horloge.maintenant = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)
    seconde = _facturer(client_gerant, devis[1]["id"])
    assert (seconde["numero"], seconde["echeance"]) == ("F-2027-001", "2027-01-31")
    assert _facturer(client_gerant, devis[2]["id"])["numero"] == "F-2027-002"


def test_une_emission_annulee_ne_laisse_pas_de_trou(
    horloge: Horloge,
    client_gerant: TestClient,
    db: Session,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    premier = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    second = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    assert _facturer(client_gerant, premier["id"])["numero"] == "F-2026-001"

    # Le numéro 002 est réservé, puis l'émission échoue : la transaction est annulée.
    with pytest.raises(IntegrityError), db.begin_nested():
        assert prochain_numero(db, "FACTURE", 2026, "F") == "F-2026-002"
        db.execute(text("INSERT INTO facture (numero) VALUES ('F-2026-002')"))

    assert _facturer(client_gerant, second["id"])["numero"] == "F-2026-002"


def test_un_refus_ne_consomme_pas_de_numero(
    horloge: Horloge, client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    en_cours = _devis(client_gerant, nouvel_ordre(StatutOT.EN_COURS), LIGNES_BACKLOG)
    termine = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)

    assert client_gerant.post(f"/devis/{en_cours['id']}/facture").status_code == 409

    assert _facturer(client_gerant, termine["id"])["numero"] == "F-2026-001"


@pytest.mark.parametrize("statut", [StatutOT.A_FAIRE, StatutOT.EN_COURS])
def test_ordre_non_termine_409(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], statut: StatutOT
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(statut), LIGNES_BACKLOG)

    reponse = client_gerant.post(f"/devis/{devis['id']}/facture")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "ordre_non_termine"
    assert reponse.json()["message"] == "La facture s'établit quand l'intervention est terminée."
    assert client_gerant.get("/factures").json()["total"] == 0


def test_devis_deja_facture_409(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    facture = _facturer(client_gerant, devis["id"])

    reponse = client_gerant.post(f"/devis/{devis['id']}/facture")

    assert reponse.status_code == 409
    corps = reponse.json()
    assert (corps["code"], corps["facture_id"], corps["numero"]) == (
        "devis_deja_facture",
        facture["id"],
        "F-2026-001",
    )


def test_devis_sans_ligne_409(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], db: Session
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    db.execute(text("DELETE FROM ligne_devis WHERE devis_id = :id"), {"id": devis["id"]})
    db.expire_all()

    reponse = client_gerant.post(f"/devis/{devis['id']}/facture")

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "devis_vide"


def test_devis_facture_n_est_plus_modifiable(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    facture = _facturer(client_gerant, devis["id"])

    reponse = client_gerant.put(f"/devis/{devis['id']}", json={"lignes": LIGNES_MAQUETTE})

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "devis_facture"
    assert reponse.json()["message"] == "Ce devis est facturé : il ne peut plus être modifié."
    assert reponse.json()["facture_id"] == facture["id"]
    assert client_gerant.get(f"/devis/{devis['id']}").json()["totaux"]["total_ttc_centimes"] == (
        16_800
    )


def test_inconnus_404(client_gerant: TestClient) -> None:
    for identifiant in (999_999, 2**40):
        assert client_gerant.post(f"/devis/{identifiant}/facture").status_code == 404
        for chemin in (f"/factures/{identifiant}", f"/factures/{identifiant}/pdf"):
            reponse = client_gerant.get(chemin)
            assert reponse.status_code == 404
            assert reponse.json()["message"] == "Facture introuvable."


def test_liste_de_la_plus_recente_a_la_plus_ancienne_et_filtre_par_jour(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    devis = [_devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG) for _ in range(2)]
    _facturer(client_gerant, devis[0]["id"])  # lundi 2 novembre
    horloge.maintenant = datetime(2026, 11, 4, 22, 30, tzinfo=UTC)  # mercredi 4, 23 h 30 Paris
    connecter(client_gerant, gerant.email)
    _facturer(client_gerant, devis[1]["id"])

    page = client_gerant.get("/factures").json()

    assert page["total"] == 2
    assert [f["numero"] for f in page["elements"]] == ["F-2026-002", "F-2026-001"]
    recente = page["elements"][0]
    assert recente["client"] == {"nom": "Laurent", "prenom": "Claire"}
    assert recente["vehicule"] == {
        "immatriculation": "GH-482-KL",
        "marque": "Peugeot",
        "modele": "308 SW",
    }
    assert recente["total_ttc_centimes"] == 16_800
    assert recente["echeance"] == "2026-12-04"
    du_4 = client_gerant.get("/factures?du=2026-11-04&au=2026-11-04").json()
    assert [f["numero"] for f in du_4["elements"]] == ["F-2026-002"]
    assert client_gerant.get("/factures?au=2026-11-03").json()["total"] == 1
    assert client_gerant.get("/factures?du=2026-11-05&au=2026-11-04").status_code == 422


# --- Immuabilité garantie par la base ---------------------------------------------------------


@pytest.mark.parametrize(
    "requete",
    [
        "UPDATE facture SET total_ttc_centimes = 1",
        "UPDATE facture SET client_fige = '{}'::jsonb",
        "DELETE FROM facture",
        "TRUNCATE facture CASCADE",
        "UPDATE ligne_facture SET designation = 'Modifiée'",
        "DELETE FROM ligne_facture",
        "TRUNCATE ligne_facture",
    ],
)
def test_la_base_refuse_de_modifier_ou_supprimer_une_facture(
    client_gerant: TestClient,
    nouvel_ordre: Callable[..., OrdreTravail],
    db: Session,
    requete: str,
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    _facturer(client_gerant, devis["id"])

    with pytest.raises(DBAPIError) as erreur, db.begin_nested():
        db.execute(text(requete))

    assert getattr(erreur.value.orig, "sqlstate", None) == "ET001"
    assert "facture immuable" in str(erreur.value.orig)
    assert db.scalar(select(Facture.total_ttc_centimes)) == 16_800


# --- PDF -------------------------------------------------------------------------------------


def _texte_pdf(contenu: bytes) -> str:
    """Texte du PDF, blancs (retours à la ligne compris) ramenés à une espace."""
    lecteur = PdfReader(BytesIO(contenu))
    return " ".join(" ".join(page.extract_text() or "" for page in lecteur.pages).split())


def test_pdf_avec_numero_totaux_mentions_client_et_vehicule(
    horloge: Horloge, client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail]
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_MAQUETTE)
    facture = _facturer(client_gerant, devis["id"])

    reponse = client_gerant.get(f"/factures/{facture['id']}/pdf")

    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/pdf"
    assert reponse.headers["content-disposition"] == 'attachment; filename="F-2026-001.pdf"'
    assert reponse.headers["cache-control"] == "no-store"
    assert reponse.content.startswith(b"%PDF-")
    texte = _texte_pdf(reponse.content)
    reglages = get_settings()
    for attendu in (
        "Facture F-2026-001",
        "454,80 €",
        "75,80 €",
        "379,00 €",
        "180,00 €",
        "199,00 €",
        "Main-d'œuvre HT",
        "TVA 20 %",
        "Total TTC",
        f"SIRET {reglages.garage_siret}",
        f"TVA intracommunautaire {reglages.garage_tva_intra}",
        reglages.garage_raison_sociale,
        reglages.garage_rcs,
        "40 €",
        "Date d'émission : 02/11/2026",
        "Date d'échéance : 02/12/2026",
        "Pas d'escompte pour paiement anticipé.",
        "Claire Laurent",
        "Tél. 06 12 48 30 75",
        "GH-482-KL",
        "Peugeot 308 SW",
        "84 312 km",
        "OT-2026-001",
        "Diagnostic freinage",
        "0,5 h",
    ):
        assert attendu in texte, attendu


def test_pdf_genere_a_partir_des_seules_donnees_figees(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], db: Session
) -> None:
    ordre = nouvel_ordre()
    devis = _devis(client_gerant, ordre, LIGNES_BACKLOG)
    facture = _facturer(client_gerant, devis["id"])
    avant = client_gerant.get(f"/factures/{facture['id']}/pdf").content

    client = ordre.vehicule.client
    client.nom, client.prenom = "Durand", "Paul"
    ordre.vehicule.immatriculation = "AB-123-CD"
    db.flush()
    apres = client_gerant.get(f"/factures/{facture['id']}/pdf").content

    assert apres == avant
    texte = _texte_pdf(apres)
    assert "Claire Laurent" in texte and "Durand" not in texte
    assert "GH-482-KL" in texte and "AB-123-CD" not in texte
    assert client_gerant.get(f"/factures/{facture['id']}").json()["client"]["nom"] == "Laurent"


def test_pdf_ecrit_les_noms_hors_winansi_sans_carre_noir(
    client_gerant: TestClient, nouvel_ordre: Callable[..., OrdreTravail], db: Session
) -> None:
    """Revue du sprint 3 : avec Helvetica (WinAnsi), « ł », « ş » ou « ễ » sortaient en « ■ »."""
    ordre = nouvel_ordre()
    client = ordre.vehicule.client
    client.nom, client.prenom = "Dvořák-Nguyễn", "Łukasz Ştefan"
    ordre.vehicule.marque, ordre.vehicule.modele = "Škoda", "Octavia Ő"
    db.flush()
    designation = "Joint torique Ø 5 mm ≤ 3 bar → kit Ő"
    lignes = [
        {"type": "piece", "reference": "JT-Ø5", "designation": designation, "quantite": "1",
         "prix_unitaire_ht_centimes": 1250},
        *LIGNES_BACKLOG,
    ]  # fmt: skip
    facture = _facturer(client_gerant, _devis(client_gerant, ordre, lignes)["id"])

    texte = _texte_pdf(client_gerant.get(f"/factures/{facture['id']}/pdf").content)

    assert "■" not in texte
    for attendu in (
        "Łukasz Ştefan Dvořák-Nguyễn",
        "Škoda Octavia Ő",
        "JT-Ø5",
        designation,
        "Main-d'œuvre HT",
        "183,00 €",  # 152,50 € HT + 30,50 € de TVA
    ):
        assert attendu in texte, attendu


# --- Accès -----------------------------------------------------------------------------------


def test_mecanicien_refuse_sur_chaque_route_de_facture(
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    autre = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)
    facture = _facturer(client_gerant, devis["id"])

    for methode, chemin in (
        ("POST", f"/devis/{autre['id']}/facture"),
        ("GET", "/factures"),
        ("GET", f"/factures/{facture['id']}"),
        ("GET", f"/factures/{facture['id']}/pdf"),
    ):
        reponse = client_mecanicien.request(methode, chemin)
        assert reponse.status_code == 403, (methode, chemin)
        assert reponse.json()["code"] == "interdit"
    assert client_gerant.get("/factures").json()["total"] == 1


def test_sans_session_401(client_anonyme: TestClient) -> None:
    for methode, chemin in (
        ("POST", "/devis/1/facture"),
        ("GET", "/factures"),
        ("GET", "/factures/1"),
        ("GET", "/factures/1/pdf"),
    ):
        assert client_anonyme.request(methode, chemin).status_code == 401


# --- Concurrence (deux connexions réelles) ----------------------------------------------------

ANNEE = 2094
MAINTENANT = datetime(ANNEE, 3, 2, 10, 0, tzinfo=UTC)


@dataclass(frozen=True)
class DonneesFacturation:
    gerant_id: int
    client_id: int
    vehicule_id: int
    ordre_ids: tuple[int, int]
    devis_ids: tuple[int, int]


@pytest.fixture
def deux_devis(engine: Engine) -> Iterator[DonneesFacturation]:
    """Deux devis d'OT « Prêt » validés en base, supprimés à la fin du test.

    La base refuse DELETE sur facture et ligne_facture : le nettoyage désactive les deux
    triggers d'immuabilité le temps de sa transaction (ALTER TABLE … DISABLE TRIGGER, en
    tant que propriétaire des tables). Le DDL étant transactionnel, aucune autre session ne
    voit jamais les triggers désactivés.
    """
    with nouvelle_session(engine) as s:
        gerant = Utilisateur(
            email="gerant.facture@garage.test",
            nom="Nadia Facture",
            role=Role.GERANT,
            mot_de_passe_hash="x",
        )
        client = Client(nom="Concurrence", prenom="Facture", telephone="0612483075")
        s.add_all([gerant, client])
        s.flush()
        vehicule = Vehicule(
            client_id=client.id,
            immatriculation="ZZ-094-ZZ",
            marque="Peugeot",
            modele="308 SW",
            kilometrage=1,
        )
        s.add(vehicule)
        ordres = [
            OrdreTravail(
                numero=f"OT-{ANNEE}-00{i}",
                vehicule=vehicule,
                demande_client="Sonde de concurrence.",
                statut=StatutOT.TERMINE,
                ouvert_le=MAINTENANT,
                createur=gerant,
            )
            for i in (1, 2)
        ]
        s.add_all(ordres)
        s.flush()
        entree = DevisEntree.model_validate({"lignes": LIGNES_BACKLOG})
        devis = [service_devis.creer_devis(s, o, entree.lignes, gerant, MAINTENANT) for o in ordres]
        for d in devis:
            changer_statut_devis(d, StatutDevis.ENVOYE, gerant, MAINTENANT)
            changer_statut_devis(d, StatutDevis.ACCEPTE, gerant, MAINTENANT)
        s.commit()
        donnees = DonneesFacturation(
            gerant.id,
            client.id,
            vehicule.id,
            (ordres[0].id, ordres[1].id),
            (devis[0].id, devis[1].id),
        )
    yield donnees
    with engine.begin() as c:
        c.execute(text("ALTER TABLE ligne_facture DISABLE TRIGGER ligne_facture_immuable"))
        c.execute(text("ALTER TABLE facture DISABLE TRIGGER facture_immuable"))
        factures = select(Facture.id).where(Facture.devis_id.in_(donnees.devis_ids))
        c.execute(delete(LigneFacture).where(LigneFacture.facture_id.in_(factures)))
        c.execute(delete(Facture).where(Facture.id.in_(factures)))
        c.execute(text("ALTER TABLE facture ENABLE TRIGGER facture_immuable"))
        c.execute(text("ALTER TABLE ligne_facture ENABLE TRIGGER ligne_facture_immuable"))
        c.execute(delete(Devis).where(Devis.id.in_(donnees.devis_ids)))
        c.execute(delete(OrdreTravail).where(OrdreTravail.id.in_(donnees.ordre_ids)))
        c.execute(delete(Vehicule).where(Vehicule.id == donnees.vehicule_id))
        c.execute(delete(Client).where(Client.id == donnees.client_id))
        c.execute(delete(Utilisateur).where(Utilisateur.id == donnees.gerant_id))
        c.execute(delete(Compteur).where(Compteur.annee == ANNEE))


def _emettre(donnees: DonneesFacturation, devis_id: int) -> Callable[[Session], Any]:
    def _post(s: Session) -> Any:
        gerant = s.get_one(Utilisateur, donnees.gerant_id)
        return routes_factures.etablir(devis_id, s, gerant, MAINTENANT, get_settings())

    return _post


def test_deux_emissions_simultanees_obtiennent_des_numeros_consecutifs(
    engine: Engine, deux_devis: DonneesFacturation
) -> None:
    attendait, issue = en_parallele(
        engine,
        _emettre(deux_devis, deux_devis.devis_ids[0]),
        _emettre(deux_devis, deux_devis.devis_ids[1]),
    )

    assert attendait, "la seconde émission doit attendre le compteur des factures"
    assert issue[0].numero == f"F-{ANNEE}-002"
    with nouvelle_session(engine) as s:
        numeros = s.scalars(
            select(Facture.numero)
            .where(Facture.devis_id.in_(deux_devis.devis_ids))
            .order_by(Facture.numero)
        ).all()
    assert numeros == [f"F-{ANNEE}-001", f"F-{ANNEE}-002"]


def test_un_meme_devis_facture_deux_fois_en_meme_temps_une_seule_facture(
    engine: Engine, deux_devis: DonneesFacturation
) -> None:
    devis_id = deux_devis.devis_ids[0]

    attendait, issue = en_parallele(
        engine, _emettre(deux_devis, devis_id), _emettre(deux_devis, devis_id)
    )

    assert attendait, "la seconde émission doit attendre le verrou du devis"
    assert isinstance(issue[0], AppError)
    assert (issue[0].status_code, issue[0].code) == (409, "devis_deja_facture")
    assert issue[0].details["numero"] == f"F-{ANNEE}-001"
    with nouvelle_session(engine) as s:
        assert s.scalars(select(Facture.numero).where(Facture.devis_id == devis_id)).all() == [
            f"F-{ANNEE}-001"
        ]
        compteur = s.get_one(Compteur, ("FACTURE", ANNEE))
        assert compteur.dernier == 1


def test_la_base_refuse_d_ajouter_une_ligne_a_une_facture_emise(
    engine: Engine, deux_devis: DonneesFacturation
) -> None:
    """Revue du sprint 3 : INSERT dans ligne_facture était accepté après l'émission (une
    ligne de 1 000,00 € s'ajoutait au PDF, les totaux restant à 168,00 €). Les lignes ne
    s'ajoutent que dans la transaction qui crée la facture."""
    with nouvelle_session(engine) as s:
        emise = _emettre(deux_devis, deux_devis.devis_ids[0])(s)
        s.commit()
        facture_id = emise.id

    with nouvelle_session(engine) as s:
        # Une autre facture créée dans la transaction n'ouvre pas la première aux ajouts.
        autre = _emettre(deux_devis, deux_devis.devis_ids[1])(s)
        with pytest.raises(DBAPIError) as erreur, s.begin_nested():
            s.execute(
                text(
                    "INSERT INTO ligne_facture (facture_id, type, designation, quantite,"
                    " prix_unitaire_ht_centimes, total_ht_centimes, position)"
                    " VALUES (:id, 'piece', 'ajout frauduleux', 1, 100000, 100000, 99)"
                ),
                {"id": facture_id},
            )
        assert getattr(erreur.value.orig, "sqlstate", None) == "ET001"
        assert "facture immuable" in str(erreur.value.orig)
        s.commit()
        assert len(autre.lignes) == len(LIGNES_BACKLOG)

    with nouvelle_session(engine) as s:
        lignes = s.scalars(select(func.count()).where(LigneFacture.facture_id == facture_id)).one()
        assert lignes == len(LIGNES_BACKLOG)


def test_echeance_selon_le_delai_de_paiement_configure(
    app: FastAPI,
    horloge: Horloge,
    client_gerant: TestClient,
    nouvel_ordre: Callable[..., OrdreTravail],
) -> None:
    reglages = get_settings().model_copy(update={"garage_delai_paiement_jours": 45})
    app.dependency_overrides[get_settings] = lambda: reglages
    devis = _devis(client_gerant, nouvel_ordre(), LIGNES_BACKLOG)

    facture = _facturer(client_gerant, devis["id"])

    assert facture["echeance"] == "2026-12-17"  # 2 novembre + 45 jours
    texte = _texte_pdf(client_gerant.get(f"/factures/{facture['id']}/pdf").content)
    assert "Date d'échéance : 17/12/2026" in texte


# --- Migrations --------------------------------------------------------------------------------


def _migration(nom: str) -> ModuleType:
    chemin = Path(__file__).resolve().parent.parent / "alembic" / "versions" / nom
    spec = importlib.util.spec_from_file_location(chemin.stem, chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_downgrade_de_0010_remet_le_compteur_des_factures_a_zero(engine: Engine) -> None:
    """Revue du sprint 3 : après downgrade puis upgrade, la facturation reprenait à
    F-AAAA-005 alors que les factures 001 à 004 n'existaient plus (trou de numérotation).
    Le downgrade s'exécute dans une transaction annulée : le DDL de PostgreSQL est
    transactionnel, la base de test reste intacte."""
    migration = _migration("20261202_0010_facture.py")
    with engine.connect() as connexion:
        transaction = connexion.begin()
        try:
            connexion.execute(
                text(
                    "INSERT INTO compteur (type, annee, dernier) VALUES"
                    " ('FACTURE', 2093, 4), ('OT', 2093, 7)"
                )
            )
            with Operations.context(MigrationContext.configure(connexion)):
                migration.downgrade()

            restants = connexion.execute(
                text("SELECT type, dernier FROM compteur WHERE annee = 2093")
            ).all()
            assert restants == [("OT", 7)]
        finally:
            transaction.rollback()
    with engine.connect() as connexion:
        assert connexion.execute(text("SELECT to_regclass('facture') IS NOT NULL")).scalar()
