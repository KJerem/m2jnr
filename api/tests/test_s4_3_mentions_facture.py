"""Mentions de la facture (art. 242 nonies A du CGI, sprint 4, complément de S4.3) : adresse
du client sur sa fiche, figée dans la facture et imprimée sur le PDF ; date de la prestation
figée à l'émission et imprimée quand elle diffère du jour d'émission ; factures déjà émises
inchangées ; le mécanicien ne voit jamais l'adresse."""

from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Client,
    Devis,
    Facture,
    OrdreTravail,
    Paiement,
    StatutOT,
    Utilisateur,
    Vehicule,
)
from app.services.donnees_demo import semer
from app.services.pdf_facture import generer_pdf, lignes_adresse, mention_prestation
from tests.conftest import Horloge, connecter
from tests.factures_anciennes import facture_sprint3
from tests.test_s4_1_devis import LIGNES_BACKLOG

REFERENCE_PDF = Path(__file__).resolve().parent / "donnees" / "facture_sprint3.pdf"

FICHE = {
    "nom": "Laurent",
    "prenom": "Claire",
    "telephone": "06 12 48 30 75",
    "email": None,
    "adresse": "14 rue des Établis",
    "code_postal": "69003",
    "ville": "Lyon",
    "consentement_rappels": False,
}


def _texte_pdf(contenu: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(contenu)).pages)


def _creer_client(c: TestClient, **champs: Any) -> Any:
    return c.post("/clients", json={**FICHE, **champs})


# --- Fiche client ----------------------------------------------------------------------------


def test_adresse_enregistree_et_rendue(client_gerant: TestClient) -> None:
    reponse = _creer_client(client_gerant, adresse="  14 rue des Établis ", ville=" Lyon ")
    assert reponse.status_code == 201, reponse.text
    corps = reponse.json()
    assert (corps["adresse"], corps["code_postal"], corps["ville"]) == (
        "14 rue des Établis",
        "69003",
        "Lyon",
    )
    fiche = client_gerant.get(f"/clients/{corps['id']}").json()
    assert (fiche["adresse"], fiche["code_postal"], fiche["ville"]) == (
        "14 rue des Établis",
        "69003",
        "Lyon",
    )
    [ligne] = client_gerant.get("/clients").json()["elements"]
    assert ligne["code_postal"] == "69003"


def test_adresse_facultative(client_gerant: TestClient) -> None:
    reponse = _creer_client(client_gerant, adresse="", code_postal="  ", ville=None)
    assert reponse.status_code == 201, reponse.text
    assert (reponse.json()["adresse"], reponse.json()["code_postal"], reponse.json()["ville"]) == (
        None,
        None,
        None,
    )


def test_adresse_modifiee(client_gerant: TestClient) -> None:
    client_id = _creer_client(client_gerant).json()["id"]
    reponse = client_gerant.put(
        f"/clients/{client_id}",
        json={**FICHE, "adresse": "7 impasse du Pont-Levis", "code_postal": "69100",
              "ville": "Villeurbanne"},
    )  # fmt: skip
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["ville"] == "Villeurbanne"
    effacee = client_gerant.put(f"/clients/{client_id}", json={**FICHE, "adresse": None})
    assert effacee.json()["adresse"] is None


@pytest.mark.parametrize(
    ("champs", "champ", "message"),
    [
        ({"code_postal": "6900"}, "code_postal", "Code postal à 5 chiffres."),
        ({"code_postal": "690033"}, "code_postal", "Code postal à 5 chiffres."),
        ({"code_postal": "69 003"}, "code_postal", "Code postal à 5 chiffres."),
        ({"code_postal": "2A004"}, "code_postal", "Code postal à 5 chiffres."),
        ({"code_postal": "６９００３"}, "code_postal", "Code postal à 5 chiffres."),
        ({"adresse": "x" * 201}, "adresse", "200 caractères maximum."),
        ({"ville": "x" * 101}, "ville", "100 caractères maximum."),
        ({"adresse": "14 rue\x00"}, "adresse", "Caractère non autorisé."),
        ({"ville": "Ly\x1bon"}, "ville", "Caractère non autorisé."),
    ],
)
def test_adresse_invalide_422(
    client_gerant: TestClient, champs: dict[str, str], champ: str, message: str
) -> None:
    reponse = _creer_client(client_gerant, **champs)
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {champ: message}


def test_la_base_refuse_un_code_postal_mal_forme(db: Session) -> None:
    with pytest.raises(Exception, match="code_postal_format"), db.begin_nested():
        db.add(Client(nom="Base", telephone="0612483075", code_postal="6900"))
        db.flush()


def test_le_mecanicien_ne_voit_jamais_l_adresse(
    client_gerant: TestClient,
    client_mecanicien: TestClient,
    db: Session,
    gerant: Utilisateur,
) -> None:
    client_id = _creer_client(client_gerant).json()["id"]
    vehicule = client_gerant.post(
        f"/clients/{client_id}/vehicules",
        json={"immatriculation": "GH-482-KL", "marque": "Peugeot", "modele": "308 SW",
              "kilometrage": 84_312},
    )  # fmt: skip
    assert vehicule.status_code == 201, vehicule.text
    ordre = client_gerant.post(
        "/ordres",
        json={"vehicule_id": vehicule.json()["id"], "demande_client": "Bruit au freinage."},
    )
    assert ordre.status_code == 201, ordre.text

    assert client_mecanicien.get(f"/clients/{client_id}").status_code == 403
    for chemin in (
        f"/ordres/{ordre.json()['id']}",
        "/ordres",
        f"/vehicules/{vehicule.json()['id']}",
        f"/vehicules/{vehicule.json()['id']}/historique",
        "/planning",
    ):
        reponse = client_mecanicien.get(chemin)
        assert reponse.status_code == 200, (chemin, reponse.text)
        assert "Établis" not in reponse.text, chemin
        assert "69003" not in reponse.text, chemin
        assert "adresse" not in reponse.text, chemin


# --- Facture : adresse figée et date de la prestation ---------------------------------------


@pytest.fixture
def ordre_avec_adresse(db: Session, gerant: Utilisateur) -> OrdreTravail:
    client = Client(
        nom="Laurent",
        prenom="Claire",
        telephone="0612483075",
        adresse="14 rue des Établis",
        code_postal="69003",
        ville="Lyon",
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
    ordre = OrdreTravail(
        numero="OT-2026-001",
        vehicule=vehicule,
        demande_client="Bruit au freinage.",
        statut=StatutOT.EN_COURS,
        ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
        createur=gerant,
    )
    db.add_all([vehicule, ordre])
    db.flush()
    return ordre


def _devis_accepte(c: TestClient, ordre_id: int) -> int:
    devis = c.post(f"/ordres/{ordre_id}/devis", json={"lignes": LIGNES_BACKLOG})
    assert devis.status_code == 201, devis.text
    for nouveau in ("envoye", "accepte"):
        assert (
            c.post(f"/devis/{devis.json()['id']}/statut", json={"nouveau": nouveau}).status_code
            == 200
        )
    return int(devis.json()["id"])


def _pret(c: TestClient, ordre_id: int) -> None:
    reponse = c.post(f"/ordres/{ordre_id}/statut", json={"nouveau": "termine"})
    assert reponse.status_code == 200, reponse.text


def _facturer(c: TestClient, devis_id: int) -> Any:
    reponse = c.post(f"/devis/{devis_id}/facture")
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_adresse_figee_dans_la_facture_et_le_pdf(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    db: Session,
    ordre_avec_adresse: OrdreTravail,
) -> None:
    connecter(client_gerant, gerant.email)
    devis_id = _devis_accepte(client_gerant, ordre_avec_adresse.id)
    _pret(client_gerant, ordre_avec_adresse.id)

    facture = _facturer(client_gerant, devis_id)

    assert facture["client"] == {
        "nom": "Laurent",
        "prenom": "Claire",
        "telephone": "0612483075",
        "email": None,
        "adresse": "14 rue des Établis",
        "code_postal": "69003",
        "ville": "Lyon",
    }
    pdf = client_gerant.get(f"/factures/{facture['id']}/pdf").content
    texte = _texte_pdf(pdf)
    assert "Claire Laurent\n14 rue des Établis\n69003 Lyon" in texte

    # La fiche change ensuite : la facture et son PDF restent tels qu'émis.
    client = ordre_avec_adresse.vehicule.client
    client.adresse, client.code_postal, client.ville = "3 quai des Pistons", "69005", "Lyon"
    db.flush()
    assert client_gerant.get(f"/factures/{facture['id']}").json()["client"] == facture["client"]
    assert client_gerant.get(f"/factures/{facture['id']}/pdf").content == pdf


def test_facture_sans_adresse_connue(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    db: Session,
    ordre_avec_adresse: OrdreTravail,
) -> None:
    client = ordre_avec_adresse.vehicule.client
    client.adresse = client.code_postal = client.ville = None
    db.flush()
    connecter(client_gerant, gerant.email)
    devis_id = _devis_accepte(client_gerant, ordre_avec_adresse.id)
    _pret(client_gerant, ordre_avec_adresse.id)
    facture = _facturer(client_gerant, devis_id)
    assert facture["client"]["adresse"] is None
    texte = _texte_pdf(client_gerant.get(f"/factures/{facture['id']}/pdf").content)
    assert "Claire Laurent\nTél. 06 12 48 30 75" in texte


def test_date_de_prestation_le_jour_du_passage_a_pret(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    ordre_avec_adresse: OrdreTravail,
) -> None:
    connecter(client_gerant, gerant.email)
    devis_id = _devis_accepte(client_gerant, ordre_avec_adresse.id)
    # « Prêt » le lundi 2 novembre à 23 h 30 à Paris (22 h 30 UTC)…
    horloge.maintenant = datetime(2026, 11, 2, 22, 30, tzinfo=UTC)
    connecter(client_gerant, gerant.email)
    _pret(client_gerant, ordre_avec_adresse.id)
    # … facture émise le mercredi 4 novembre à 9 h 00.
    horloge.maintenant = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)
    connecter(client_gerant, gerant.email)

    facture = _facturer(client_gerant, devis_id)

    assert facture["date_prestation"] == "2026-11-02"
    texte = _texte_pdf(client_gerant.get(f"/factures/{facture['id']}/pdf").content)
    assert "Date d'émission : 04/11/2026" in texte
    assert "Prestation réalisée le 02/11/2026" in texte


def test_date_de_prestation_a_l_heure_de_paris(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    ordre_avec_adresse: OrdreTravail,
) -> None:
    connecter(client_gerant, gerant.email)
    devis_id = _devis_accepte(client_gerant, ordre_avec_adresse.id)
    # Lundi 2 novembre à 23 h 30 UTC = mardi 3 novembre à 0 h 30 à Paris.
    horloge.maintenant = datetime(2026, 11, 2, 23, 30, tzinfo=UTC)
    connecter(client_gerant, gerant.email)
    _pret(client_gerant, ordre_avec_adresse.id)
    horloge.avancer(hours=9)

    facture = _facturer(client_gerant, devis_id)

    assert facture["date_prestation"] == "2026-11-03"
    texte = _texte_pdf(client_gerant.get(f"/factures/{facture['id']}/pdf").content)
    assert "Prestation réalisée" not in texte  # même jour que l'émission, à Paris


def test_date_de_prestation_a_defaut_la_cloture(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    db: Session,
    ordre_avec_adresse: OrdreTravail,
) -> None:
    connecter(client_gerant, gerant.email)
    devis_id = _devis_accepte(client_gerant, ordre_avec_adresse.id)
    # OT livré sans trace du passage à « Prêt » (donnée reprise) : la clôture fait foi.
    ordre_avec_adresse.statut = StatutOT.LIVRE
    ordre_avec_adresse.cloture_le = datetime(2026, 11, 2, 16, 0, tzinfo=UTC)
    db.flush()
    horloge.avancer(days=3)
    connecter(client_gerant, gerant.email)

    facture = _facturer(client_gerant, devis_id)

    assert facture["date_prestation"] == "2026-11-02"
    texte = _texte_pdf(client_gerant.get(f"/factures/{facture['id']}/pdf").content)
    assert "Prestation réalisée le 02/11/2026" in texte


def test_sans_pret_ni_cloture_pas_de_date_de_prestation(
    horloge: Horloge,
    client_gerant: TestClient,
    gerant: Utilisateur,
    db: Session,
    ordre_avec_adresse: OrdreTravail,
) -> None:
    connecter(client_gerant, gerant.email)
    devis_id = _devis_accepte(client_gerant, ordre_avec_adresse.id)
    ordre_avec_adresse.statut = StatutOT.TERMINE
    db.flush()
    facture = _facturer(client_gerant, devis_id)
    assert facture["date_prestation"] is None
    assert "Prestation réalisée" not in _texte_pdf(
        client_gerant.get(f"/factures/{facture['id']}/pdf").content
    )


# --- Factures déjà émises ---------------------------------------------------------------------


def test_le_pdf_d_une_facture_deja_emise_est_inchange() -> None:
    """Octets identiques au PDF produit par le code du sprint 3, avant les mentions."""
    assert generer_pdf(facture_sprint3()) == REFERENCE_PDF.read_bytes()


def test_une_facture_deja_emise_se_lit_sans_adresse_ni_date(
    client_gerant: TestClient, db: Session, gerant: Utilisateur
) -> None:
    client = Client(nom="Ancien", telephone="0612483075", adresse="Rue nouvelle")
    db.add(client)
    db.flush()
    vehicule = Vehicule(
        client_id=client.id, immatriculation="ZZ-015-ZZ", marque="Peugeot", modele="308",
        kilometrage=1,
    )  # fmt: skip
    ordre = OrdreTravail(
        numero="OT-2026-015",
        vehicule=vehicule,
        demande_client="Reprise.",
        statut=StatutOT.LIVRE,
        ouvert_le=datetime(2026, 12, 1, 8, tzinfo=UTC),
        createur=gerant,
    )
    db.add_all([vehicule, ordre])
    db.flush()
    connexion = db.connection()
    devis_id = connexion.execute(
        text(
            "INSERT INTO devis (ordre_travail_id, total_ht_centimes, total_tva_centimes,"
            " total_ttc_centimes, cree_par, statut, envoye_le, decide_le, decide_par)"
            " VALUES (:o, 0, 0, 0, :g, 'accepte', now(), now(), :g) RETURNING id"
        ),
        {"o": ordre.id, "g": gerant.id},
    ).scalar_one()
    # Copie figée du sprint 3 : ni adresse ni date de prestation.
    facture_id = connexion.execute(
        text(
            "INSERT INTO facture (numero, devis_id, ordre_travail_id, emise_le, echeance,"
            " client_fige, vehicule_fige, garage_fige, taux_tva_bp, total_ht_centimes,"
            " total_tva_centimes, total_ttc_centimes, cree_par) VALUES ('F-2026-015', :d, :o,"
            " '2026-12-04T09:40:00Z', '2027-01-03',"
            ' \'{"nom": "Ancien", "prenom": null, "telephone": "0612483075",'
            ' "email": null}\','
            ' \'{"immatriculation": "ZZ-015-ZZ", "marque": "Peugeot", "modele": "308",'
            ' "kilometrage": 1}\', CAST(:garage AS jsonb), 2000, 0, 0, 0, :g) RETURNING id'
        ),
        {
            "d": devis_id,
            "o": ordre.id,
            "g": gerant.id,
            "garage": '{"raison_sociale": "G", "adresse": "A", "siret": "S",'
            ' "tva_intracommunautaire": "T", "capital": "C", "rcs": "R", "telephone": "0",'
            ' "email": "e"}',
        },
    ).scalar_one()

    corps = client_gerant.get(f"/factures/{facture_id}").json()

    assert corps["date_prestation"] is None
    assert (corps["client"]["adresse"], corps["client"]["code_postal"]) == (None, None)
    texte = _texte_pdf(client_gerant.get(f"/factures/{facture_id}/pdf").content)
    assert "Rue nouvelle" not in texte
    assert "Prestation réalisée" not in texte


# --- Règles pures du PDF ------------------------------------------------------------------------


def test_lignes_de_l_adresse() -> None:
    assert lignes_adresse({"nom": "X"}) == []
    assert lignes_adresse({"adresse": "14 rue des Établis", "code_postal": "69003",
                           "ville": "Lyon"}) == ["14 rue des Établis", "69003 Lyon"]  # fmt: skip
    assert lignes_adresse({"adresse": None, "code_postal": None, "ville": "Lyon"}) == ["Lyon"]


def test_mention_de_la_prestation() -> None:
    facture = facture_sprint3()  # émise le 4 décembre 2026 à 10 h 40 (Paris)
    assert mention_prestation(facture, "Europe/Paris") is None
    facture.date_prestation = date(2026, 12, 4)
    assert mention_prestation(facture, "Europe/Paris") is None
    facture.date_prestation = date(2026, 12, 3)
    assert mention_prestation(facture, "Europe/Paris") == "Prestation réalisée le 03/12/2026"


# --- Jeu de démonstration ------------------------------------------------------------------


def test_seed_adresses_statuts_des_devis_et_paiements(db: Session) -> None:
    reglages = get_settings().model_copy(
        update={"demo_password_gerant": "demo-g-2026", "demo_password_mecanicien": "demo-m-2026"}
    )
    # Lundi 16 novembre 2026, 15 h 00 à Paris.
    maintenant = datetime(2026, 11, 16, 14, 0, tzinfo=UTC)
    semer(db, reglages, maintenant)

    clients = db.scalars(select(Client)).all()
    assert all(c.adresse and c.code_postal and c.ville for c in clients)
    statuts = {
        d.ordre.vehicule.immatriculation + " " + d.ordre.demande_client[:12]: d for d in
        db.scalars(select(Devis)).all()
    }  # fmt: skip
    peugeot = statuts["GH-482-KL Bruit au fre"]
    assert peugeot.statut.value == "accepte"
    assert peugeot.decide_le == datetime(2026, 11, 16, 8, 40, tzinfo=UTC)  # 9 h 40 à Paris
    clio = statuts["FD-119-RT Voyant moteu"]
    assert (clio.statut.value, clio.total_ttc_centimes) == ("envoye", 61_240)
    assert statuts["HB-205-MZ Démarrage di"].statut.value == "accepte"

    paiements = {
        f.numero: [(p.mode.value, p.montant_centimes) for p in f.paiements]
        for f in db.scalars(select(Facture)).all()
    }
    assert paiements == {
        "F-2025-001": [("cheque", 17_112)],
        "F-2026-001": [("carte", 29_820)],
        "F-2026-002": [("especes", 5_000)],
    }
    revision = db.scalars(select(Facture).where(Facture.numero == "F-2025-001")).one()
    assert revision.date_prestation == date(2025, 11, 16)
    assert revision.client_fige["ville"] == "Lyon"

    # Rejoué : rien de plus, aucune facture touchée.
    semer(db, reglages, maintenant)
    assert db.scalar(select(func.count()).select_from(Paiement)) == 3
