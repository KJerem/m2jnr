"""Story S1.3 — recherche du gérant par nom, téléphone, immatriculation, numéro d'OT ou de
facture ; message clair (liste vide) si aucun résultat ; 422 si la saisie est trop courte."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Client, OrdreTravail, StatutOT, Utilisateur, Vehicule
from app.services.recherche import (
    MESSAGE_TROP_COURT,
    MESSAGE_TROP_LONG,
    RESULTATS_MAX,
    analyser_requete,
    echapper_like,
)
from tests.conftest import Horloge
from tests.test_s4_1_devis import LIGNES_BACKLOG


def _client(db: Session, nom: str, prenom: str | None, telephone: str, *plaques: str) -> Client:
    client = Client(nom=nom, prenom=prenom, telephone=telephone)
    db.add(client)
    db.flush()
    for plaque in plaques:
        db.add(
            Vehicule(
                client_id=client.id,
                immatriculation=plaque,
                marque="Peugeot",
                modele="308 SW",
                kilometrage=84_312,
            )
        )
    db.flush()
    return client


def _ordre(db: Session, gerant: Utilisateur, plaque: str, numero: str, statut: StatutOT) -> Any:
    vehicule = db.scalars(select(Vehicule).where(Vehicule.immatriculation == plaque)).one()
    ordre = OrdreTravail(
        numero=numero,
        vehicule=vehicule,
        demande_client="Bruit au freinage.",
        statut=statut,
        ouvert_le=datetime(2026, 11, 2, 7, 10, tzinfo=UTC),
        createur=gerant,
    )
    db.add(ordre)
    db.flush()
    return ordre


@pytest.fixture
def fichier(db: Session, gerant: Utilisateur) -> dict[str, Any]:
    """Les clients des maquettes, dont un nom accentué et un prénom composé."""
    claire = _client(db, "Laurent", "Claire", "0612483075", "GH-482-KL")
    helene = _client(db, "Lefèvre", "Hélène", "0478214455", "FD-301-RT")
    moussa = _client(db, "Diallo", "Moussa", "0645716308", "AB-123-CD", "EF-456-GH")
    obrien = _client(db, "O'Brien", "Seán", "0700112233")
    ordre = _ordre(db, gerant, "GH-482-KL", "OT-2026-003", StatutOT.EN_COURS)
    return {"claire": claire, "helene": helene, "moussa": moussa, "obrien": obrien, "ordre": ordre}


def _chercher(c: TestClient, q: str) -> dict[str, Any]:
    reponse = c.get("/recherche", params={"q": q})
    assert reponse.status_code == 200, reponse.text
    return dict(reponse.json())


def _noms(resultats: dict[str, Any]) -> list[str]:
    return [f"{c['prenom']} {c['nom']}" for c in resultats["clients"]]


# --- Lecture de la saisie (fonction pure) ------------------------------------------------------


@pytest.mark.parametrize(
    ("saisie", "telephone"),
    [
        ("06 12 48", "061248"),
        ("+33 6 12 48 30 75", "0612483075"),
        ("0033 6 12 48 30 75", "0612483075"),
        ("06.12.48.30.75", "0612483075"),
        ("(04) 78-21", "047821"),
        ("4830", "4830"),
        ("Diallo", None),
        ("GH482KL", None),
        ("+44 20 7946", None),
        ("06+12", None),
    ],
)
def test_lecture_du_telephone(saisie: str, telephone: str | None) -> None:
    assert analyser_requete(saisie).telephone == telephone


@pytest.mark.parametrize(
    ("saisie", "plaque"),
    [
        ("gh482kl", "GH482KL"),
        ("GH-482-KL", "GH482KL"),
        ("gh 482", "GH482"),
        ("482", None),
        ("Diallo", None),
        ("06 12 48", None),
    ],
)
def test_lecture_de_la_plaque(saisie: str, plaque: str | None) -> None:
    assert analyser_requete(saisie).plaque == plaque


@pytest.mark.parametrize(
    ("saisie", "ordre", "facture"),
    [
        ("OT-2026-003", "OT-2026-003", None),
        ("ot 2026 003", "OT-2026-003", None),
        ("OT2026", "OT-2026-", None),
        ("F-2026-001", None, "F-2026-001"),
        ("f-2026-0", None, "F-2026-0"),
        ("2026-003", "OT-2026-003", "F-2026-003"),
        ("Diallo", None, None),
    ],
)
def test_lecture_des_numeros(saisie: str, ordre: str | None, facture: str | None) -> None:
    criteres = analyser_requete(saisie)
    assert (criteres.ordre, criteres.facture) == (ordre, facture)


def test_mots_separes_par_les_espaces() -> None:
    assert analyser_requete("  moussa   diallo ").mots == ("moussa", "diallo")


def test_echappement_des_jokers_like() -> None:
    assert echapper_like(r"50 %_\x") == r"50 \%\_\\x"


# --- Par nom -----------------------------------------------------------------------------------


@pytest.mark.parametrize("saisie", ["helene", "HÉLÈNE", "Hélène", "lefevre", "LEFÈVRE", "efèv"])
def test_nom_sans_tenir_compte_des_accents_ni_de_la_casse(
    client_gerant: TestClient, fichier: dict[str, Any], saisie: str
) -> None:
    resultats = _chercher(client_gerant, saisie)
    assert _noms(resultats) == ["Hélène Lefèvre"]
    assert resultats["q"] == saisie
    assert [v["immatriculation"] for v in resultats["vehicules"]] == ["FD-301-RT"]


@pytest.mark.parametrize("saisie", ["moussa diallo", "Diallo Moussa", "dial mou"])
def test_prenom_et_nom(client_gerant: TestClient, fichier: dict[str, Any], saisie: str) -> None:
    resultats = _chercher(client_gerant, saisie)
    assert resultats["clients"] == [
        {
            "id": fichier["moussa"].id,
            "nom": "Diallo",
            "prenom": "Moussa",
            "telephone": "0645716308",
            "nb_vehicules": 2,
        }
    ]
    assert sorted(v["immatriculation"] for v in resultats["vehicules"]) == [
        "AB-123-CD",
        "EF-456-GH",
    ]
    vehicule = resultats["vehicules"][0]
    assert vehicule["proprietaire"] == {
        "id": fichier["moussa"].id,
        "nom": "Diallo",
        "prenom": "Moussa",
    }


def test_chaque_mot_doit_se_trouver_dans_le_nom_ou_le_prenom(
    client_gerant: TestClient, fichier: dict[str, Any]
) -> None:
    assert _chercher(client_gerant, "moussa laurent")["clients"] == []


def test_apostrophe_prise_a_la_lettre(client_gerant: TestClient, fichier: dict[str, Any]) -> None:
    assert _noms(_chercher(client_gerant, "o'brien")) == ["Seán O'Brien"]
    assert _noms(_chercher(client_gerant, "sean")) == ["Seán O'Brien"]


def test_clients_par_pertinence_puis_par_nom(client_gerant: TestClient, db: Session) -> None:
    _client(db, "Martinez", "Laura", "0611111111")
    _client(db, "Martin", "Paul", "0622222222")
    _client(db, "Bertin", "Martine", "0633333333")
    resultats = _chercher(client_gerant, "martin")
    assert _noms(resultats)[0] == "Paul Martin"
    assert set(_noms(resultats)) == {"Paul Martin", "Laura Martinez", "Martine Bertin"}


# --- Par téléphone -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "saisie", ["06 12 48", "+33 6 12 48 30 75", "0033612483075", "06.12.48.30.75", "483075"]
)
def test_telephone_complet_ou_partiel(
    client_gerant: TestClient, fichier: dict[str, Any], saisie: str
) -> None:
    resultats = _chercher(client_gerant, saisie)
    assert _noms(resultats) == ["Claire Laurent"]
    assert [v["immatriculation"] for v in resultats["vehicules"]] == ["GH-482-KL"]


def test_telephone_partage_par_plusieurs_clients(
    client_gerant: TestClient, fichier: dict[str, Any]
) -> None:
    # « 06 » se trouve dans trois numéros (et dans aucun nom).
    assert set(_noms(_chercher(client_gerant, "06"))) == {"Claire Laurent", "Moussa Diallo"}


# --- Par immatriculation -----------------------------------------------------------------------


@pytest.mark.parametrize("saisie", ["gh482kl", "GH-482-KL", "gh-482", "482k", "h482"])
def test_plaque_sans_tirets_et_sans_casse(
    client_gerant: TestClient, fichier: dict[str, Any], saisie: str
) -> None:
    resultats = _chercher(client_gerant, saisie)
    assert [v["immatriculation"] for v in resultats["vehicules"]] == ["GH-482-KL"]
    assert resultats["vehicules"][0]["proprietaire"]["nom"] == "Laurent"
    # Le propriétaire et les OT du véhicule sont aussi proposés.
    assert _noms(resultats) == ["Claire Laurent"]
    assert [o["numero"] for o in resultats["ordres"]] == ["OT-2026-003"]


def test_plaque_exacte_avant_les_plaques_qui_la_contiennent(
    client_gerant: TestClient, db: Session
) -> None:
    _client(db, "Durand", "Alice", "0611111111", "AB-123-CA")
    _client(db, "Zola", "Émile", "0622222222", "AB-123-CD")
    _client(db, "Adam", "Bruno", "0633333333", "XA-123-CD")
    resultats = _chercher(client_gerant, "ab123cd")
    assert [v["immatriculation"] for v in resultats["vehicules"]] == ["AB-123-CD"]
    resultats = _chercher(client_gerant, "123c")
    # Toutes contiennent « 123C » : rangées par nom du propriétaire (Adam, Durand, Zola).
    assert [v["immatriculation"] for v in resultats["vehicules"]] == [
        "XA-123-CD",
        "AB-123-CA",
        "AB-123-CD",
    ]


# --- Par numéro d'OT ou de facture ---------------------------------------------------------------


@pytest.mark.parametrize("saisie", ["OT-2026-003", "ot-2026-003", "2026-003", "OT-2026"])
def test_numero_d_ordre_de_travail(
    client_gerant: TestClient, fichier: dict[str, Any], saisie: str
) -> None:
    resultats = _chercher(client_gerant, saisie)
    assert resultats["ordres"] == [
        {
            "id": fichier["ordre"].id,
            "numero": "OT-2026-003",
            "statut": "en_cours",
            "immatriculation": "GH-482-KL",
            "marque": "Peugeot",
            "modele": "308 SW",
        }
    ]


def test_numero_de_facture(
    horloge: Horloge,
    client_gerant: TestClient,
    db: Session,
    gerant: Utilisateur,
    fichier: dict[str, Any],
) -> None:
    ordre = _ordre(db, gerant, "FD-301-RT", "OT-2026-004", StatutOT.TERMINE)
    devis = client_gerant.post(f"/ordres/{ordre.id}/devis", json={"lignes": LIGNES_BACKLOG})
    assert devis.status_code == 201, devis.text
    for nouveau in ("envoye", "accepte"):
        reponse = client_gerant.post(
            f"/devis/{devis.json()['id']}/statut", json={"nouveau": nouveau}
        )
        assert reponse.status_code == 200, reponse.text
    facture = client_gerant.post(f"/devis/{devis.json()['id']}/facture")
    assert facture.status_code == 201, facture.text
    numero = facture.json()["numero"]
    assert numero == "F-2026-001"

    for saisie in ("F-2026-001", "f-2026-001", "F2026", "2026-001"):
        resultats = _chercher(client_gerant, saisie)
        assert resultats["factures"] == [
            {
                "id": facture.json()["id"],
                "numero": "F-2026-001",
                "emise_le": "2026-11-02T13:47:00Z",
                "total_ttc_centimes": 16_800,
                "client": {"nom": "Lefèvre", "prenom": "Hélène"},
            }
        ], saisie
    assert _chercher(client_gerant, "F-2026-002")["factures"] == []


# --- Aucun résultat, saisie invalide, sécurité -------------------------------------------------


def test_aucun_resultat_listes_vides(client_gerant: TestClient, fichier: dict[str, Any]) -> None:
    assert _chercher(client_gerant, "  xyzzy  ") == {
        "q": "xyzzy",
        "clients": [],
        "vehicules": [],
        "ordres": [],
        "factures": [],
    }


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({}, MESSAGE_TROP_COURT),
        ({"q": ""}, MESSAGE_TROP_COURT),
        ({"q": "a"}, MESSAGE_TROP_COURT),
        ({"q": "   b   "}, MESSAGE_TROP_COURT),
        ({"q": "x" * 101}, MESSAGE_TROP_LONG),
        ({"q": "dia\x00llo"}, "Caractère non autorisé."),
    ],
)
def test_saisie_invalide_422(
    client_gerant: TestClient, params: dict[str, str], message: str
) -> None:
    reponse = client_gerant.get("/recherche", params=params)
    assert reponse.status_code == 422
    assert reponse.json() == {"code": "validation", "message": message, "champs": {"q": message}}


def test_cent_caracteres_acceptes(client_gerant: TestClient) -> None:
    assert _chercher(client_gerant, "x" * 100)["clients"] == []


@pytest.mark.parametrize("saisie", ["%%", "__", "%_", "\\%", "a%", "_e"])
def test_jokers_like_pris_a_la_lettre(
    client_gerant: TestClient, fichier: dict[str, Any], saisie: str
) -> None:
    resultats = _chercher(client_gerant, saisie)
    assert resultats["clients"] == resultats["vehicules"] == resultats["ordres"] == []


def test_jokers_trouves_quand_ils_sont_dans_le_nom(client_gerant: TestClient, db: Session) -> None:
    _client(db, "Garage_50%", None, "0611111111")
    _client(db, "Garage X 50", None, "0622222222")
    assert [c["nom"] for c in _chercher(client_gerant, "e_50%")["clients"]] == ["Garage_50%"]


def test_injection_sql_sans_effet(client_gerant: TestClient, fichier: dict[str, Any]) -> None:
    for saisie in ("'; DROP TABLE client; --", "' OR '1'='1", 'Diallo" --'):
        assert _chercher(client_gerant, saisie)["clients"] == []
    assert _noms(_chercher(client_gerant, "diallo")) == ["Moussa Diallo"]


def test_vingt_resultats_au_plus_par_rubrique(client_gerant: TestClient, db: Session) -> None:
    for i in range(RESULTATS_MAX + 3):
        _client(db, f"Bernard{i:02d}", "Jean", f"06{i:08d}", f"AA-{100 + i}-BB")
    resultats = _chercher(client_gerant, "bernard")
    assert len(resultats["clients"]) == RESULTATS_MAX
    assert len(resultats["vehicules"]) == RESULTATS_MAX
    # Même pertinence : rangés par nom.
    assert resultats["clients"][0]["nom"] == "Bernard00"


@contextmanager
def _compter_requetes(db: Session) -> Iterator[list[str]]:
    requetes: list[str] = []

    def _noter(*args: Any) -> None:
        requetes.append(str(args[2]))

    connexion = db.connection()
    event.listen(connexion, "before_cursor_execute", _noter)
    try:
        yield requetes
    finally:
        event.remove(connexion, "before_cursor_execute", _noter)


def test_nombre_de_requetes_independant_du_nombre_de_resultats(
    client_gerant: TestClient, db: Session, gerant: Utilisateur
) -> None:
    _client(db, "Petit", "Ana", "0611111111", "AB-101-CD")
    _ordre(db, gerant, "AB-101-CD", "OT-2026-101", StatutOT.A_FAIRE)
    with _compter_requetes(db) as peu:
        _chercher(client_gerant, "petit")
    for i in range(8):
        _client(db, f"Petit{i}", "Ana", f"07{i:08d}", f"AB-2{i}0-CD")
        _ordre(db, gerant, f"AB-2{i}0-CD", f"OT-2026-2{i}0", StatutOT.A_FAIRE)
    with _compter_requetes(db) as beaucoup:
        resultats = _chercher(client_gerant, "petit")
    assert len(resultats["clients"]) == 9
    assert len(beaucoup) == len(peu)


# --- Accès ---------------------------------------------------------------------------------


def test_mecanicien_refuse_403(client_mecanicien: TestClient) -> None:
    reponse = client_mecanicien.get("/recherche", params={"q": "diallo"})
    assert reponse.status_code == 403


def test_sans_session_401(client_anonyme: TestClient) -> None:
    assert client_anonyme.get("/recherche", params={"q": "diallo"}).status_code == 401
