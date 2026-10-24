"""Story S1.2 — fiche véhicule : plaque SIV unique, kilométrage, client existant, accès."""

import re
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Client, Vehicule
from app.services.donnees_demo import semer
from app.services.immatriculation import (
    MESSAGE_IMMATRICULATION_INVALIDE,
    MESSAGE_VIN_INVALIDE,
    normaliser_immatriculation,
    normaliser_vin,
)
from tests.conftest import Horloge


def _vehicule(**surcharges: Any) -> dict[str, Any]:
    corps: dict[str, Any] = {
        "immatriculation": "GH-482-KL",
        "marque": "Peugeot",
        "modele": "308 SW",
        "kilometrage": 84312,
        "vin": "VF3LCYHZPKS123456",
        "date_mise_en_circulation": "2019-03-01",
    }
    corps.update(surcharges)
    return corps


@pytest.fixture
def client_id(client_gerant: TestClient) -> int:
    reponse = client_gerant.post(
        "/clients", json={"nom": "Laurent", "prenom": "Claire", "telephone": "0612345678"}
    )
    return int(reponse.json()["id"])


def _ajouter(c: TestClient, client_id: int, **surcharges: Any):  # type: ignore[no-untyped-def]
    return c.post(f"/clients/{client_id}/vehicules", json=_vehicule(**surcharges))


# --- Normalisation (fonctions pures) --------------------------------------------------------


@pytest.mark.parametrize(
    "saisie", ["GH-482-KL", "gh-482-kl", "GH482KL", "gh 482 kl", " Gh-482 kL "]
)
def test_normalisation_de_l_immatriculation(saisie: str) -> None:
    assert normaliser_immatriculation(saisie) == "GH-482-KL"


@pytest.mark.parametrize(
    "saisie",
    [
        "",
        "GH-48-KL",
        "GH-4823-KL",
        "G1-482-KL",
        "GH-000-KL",
        "IH-482-KL",
        "GO-482-KL",
        "GH-482-KU",
        "123-AB-45",
        "GH_482_KL",
    ],
)
def test_immatriculation_invalide(saisie: str) -> None:
    with pytest.raises(ValueError, match=re.escape(MESSAGE_IMMATRICULATION_INVALIDE)):
        normaliser_immatriculation(saisie)


def test_normalisation_du_vin() -> None:
    assert normaliser_vin(" vf3lcyhzpks123456 ") == "VF3LCYHZPKS123456"
    for invalide in (
        "VF3LCYHZPKS12345",
        "VF3LCYHZPKS1234567",
        "VF3LCYHZPKS12345I",
        "OF3LCYHZPKS123456",
        "QF3LCYHZPKS123456",
    ):
        with pytest.raises(ValueError, match="VIN invalide"):
            normaliser_vin(invalide)


# --- Création -------------------------------------------------------------------------------


def test_creation_d_un_vehicule_rattache_au_client(
    client_gerant: TestClient, client_id: int
) -> None:
    reponse = _ajouter(
        client_gerant, client_id, immatriculation="gh 482 kl", vin="vf3lcyhzpks123456"
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["immatriculation"] == "GH-482-KL"
    assert corps["vin"] == "VF3LCYHZPKS123456"
    assert corps["client_id"] == client_id
    assert corps["proprietaire"] == {"id": client_id, "nom": "Laurent", "prenom": "Claire"}
    fiche_client = client_gerant.get(f"/clients/{client_id}").json()
    assert fiche_client["nombre_vehicules"] == 1
    assert fiche_client["vehicules"] == [
        {
            "id": corps["id"],
            "immatriculation": "GH-482-KL",
            "marque": "Peugeot",
            "modele": "308 SW",
            "kilometrage": 84312,
        }
    ]
    liste = client_gerant.get(f"/clients/{client_id}/vehicules").json()
    assert [v["id"] for v in liste] == [corps["id"]]


def test_champs_facultatifs(client_gerant: TestClient, client_id: int) -> None:
    reponse = _ajouter(client_gerant, client_id, vin="", date_mise_en_circulation=None)

    assert reponse.status_code == 201
    assert reponse.json()["vin"] is None
    assert reponse.json()["date_mise_en_circulation"] is None


@pytest.mark.parametrize("variante", ["gh482kl", "GH 482 KL", "gh-482-KL"])
def test_immatriculation_en_double_casse_et_tirets_ignores(
    client_gerant: TestClient, client_id: int, variante: str
) -> None:
    premier = _ajouter(client_gerant, client_id).json()

    reponse = _ajouter(client_gerant, client_id, immatriculation=variante)

    assert reponse.status_code == 409
    assert reponse.json() == {
        "code": "immatriculation_existante",
        "message": "Cette immatriculation est déjà enregistrée.",
        "champs": {},
        "vehicule_id": premier["id"],
    }


def test_format_d_immatriculation_invalide(client_gerant: TestClient, client_id: int) -> None:
    reponse = _ajouter(client_gerant, client_id, immatriculation="AB-000-CD")

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"immatriculation": MESSAGE_IMMATRICULATION_INVALIDE}


@pytest.mark.parametrize(
    ("kilometrage", "message"),
    [
        (-1, "Doit être supérieur ou égal à 0."),
        ("abc", "Nombre entier attendu."),
        ("12000", "Nombre entier attendu."),
        (12.5, "Nombre entier attendu."),
        (2_000_001, "Doit être inférieur ou égal à 2000000."),
        (None, "Nombre entier attendu."),
    ],
)
def test_kilometrage_negatif_ou_non_numerique(
    client_gerant: TestClient, client_id: int, kilometrage: Any, message: str
) -> None:
    reponse = _ajouter(client_gerant, client_id, kilometrage=kilometrage)

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"kilometrage": message}


def test_kilometrage_zero_accepte(client_gerant: TestClient, client_id: int) -> None:
    assert _ajouter(client_gerant, client_id, kilometrage=0).status_code == 201


def test_vin_invalide(client_gerant: TestClient, client_id: int) -> None:
    reponse = _ajouter(client_gerant, client_id, vin="VF3LCYHZPKS12345O")

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"vin": MESSAGE_VIN_INVALIDE}


def test_marque_et_modele_obligatoires(client_gerant: TestClient, client_id: int) -> None:
    corps = _vehicule(marque="  ")
    del corps["modele"]

    reponse = client_gerant.post(f"/clients/{client_id}/vehicules", json=corps)

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "marque": "Champ obligatoire.",
        "modele": "Champ obligatoire.",
    }


def test_date_de_mise_en_circulation_dans_le_futur_refusee(
    horloge: Horloge, client_gerant: TestClient, client_id: int
) -> None:
    # Horloge : lundi 2 novembre 2026 à Paris.
    assert (
        _ajouter(client_gerant, client_id, date_mise_en_circulation="2026-11-03").status_code == 422
    )
    reponse = _ajouter(client_gerant, client_id, date_mise_en_circulation="2026-11-02")
    assert reponse.status_code == 201


def test_date_mal_formee(client_gerant: TestClient, client_id: int) -> None:
    reponse = _ajouter(client_gerant, client_id, date_mise_en_circulation="2019-13")

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"date_mise_en_circulation": "Date invalide."}


def test_client_inexistant_404(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients/999999/vehicules", json=_vehicule())

    assert reponse.status_code == 404
    assert reponse.json()["message"] == "Client introuvable."
    assert client_gerant.get("/clients/999999/vehicules").status_code == 404


def test_la_base_refuse_un_vehicule_sans_client_et_un_kilometrage_negatif(db: Session) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO vehicule (client_id, immatriculation, marque, modele, kilometrage)"
                " VALUES (999999, 'AB-123-CD', 'Renault', 'Clio', 10)"
            )
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("INSERT INTO client (nom, telephone) VALUES ('Test', '0600000000')"))
        db.execute(
            text(
                "INSERT INTO vehicule (client_id, immatriculation, marque, modele, kilometrage)"
                " SELECT id, 'AB-123-CD', 'Renault', 'Clio', -5 FROM client WHERE nom = 'Test'"
            )
        )


# --- Modification ---------------------------------------------------------------------------


def test_modification_d_un_vehicule(client_gerant: TestClient, client_id: int) -> None:
    vehicule = _ajouter(client_gerant, client_id).json()

    reponse = client_gerant.put(
        f"/vehicules/{vehicule['id']}", json=_vehicule(kilometrage=90000, immatriculation="gh482kl")
    )

    assert reponse.status_code == 200
    assert reponse.json()["kilometrage"] == 90000
    assert reponse.json()["immatriculation"] == "GH-482-KL"


def test_modification_vers_une_plaque_deja_prise(client_gerant: TestClient, client_id: int) -> None:
    premier = _ajouter(client_gerant, client_id).json()
    second = _ajouter(client_gerant, client_id, immatriculation="EK-730-PA", vin=None).json()

    reponse = client_gerant.put(
        f"/vehicules/{second['id']}", json=_vehicule(immatriculation="gh-482-kl")
    )

    assert reponse.status_code == 409
    assert reponse.json()["vehicule_id"] == premier["id"]


def test_vehicule_inconnu_404(client_gerant: TestClient) -> None:
    assert client_gerant.get("/vehicules/999999").status_code == 404
    assert client_gerant.put("/vehicules/999999", json=_vehicule()).status_code == 404


# --- Accès ----------------------------------------------------------------------------------


def test_mecanicien_lit_le_vehicule_sans_les_coordonnees_du_proprietaire(
    client_gerant: TestClient, client_mecanicien: TestClient, client_id: int
) -> None:
    vehicule = _ajouter(client_gerant, client_id).json()

    reponse = client_mecanicien.get(f"/vehicules/{vehicule['id']}")

    assert reponse.status_code == 200
    assert reponse.json()["proprietaire"] == {"id": client_id, "nom": "Laurent", "prenom": "Claire"}
    assert "telephone" not in str(reponse.json())


def test_mecanicien_refuse_en_ecriture(
    client_gerant: TestClient, client_mecanicien: TestClient, client_id: int
) -> None:
    vehicule = _ajouter(client_gerant, client_id).json()

    assert (
        client_mecanicien.post(f"/clients/{client_id}/vehicules", json=_vehicule()).status_code
        == 403
    )
    assert (
        client_mecanicien.put(f"/vehicules/{vehicule['id']}", json=_vehicule()).status_code == 403
    )
    assert client_mecanicien.get(f"/clients/{client_id}/vehicules").status_code == 403


def test_sans_session_401(client_anonyme: TestClient) -> None:
    assert client_anonyme.get("/vehicules/1").status_code == 401
    assert client_anonyme.put("/vehicules/1", json=_vehicule()).status_code == 401


# --- Jeu de démonstration -------------------------------------------------------------------


def test_seed_des_clients_et_vehicules_de_demo_idempotent(db: Session) -> None:
    reglages = get_settings().model_copy(
        update={"demo_password_gerant": "demo-g", "demo_password_mecanicien": "demo-m"}
    )
    semer(db, reglages)
    semer(db, reglages)

    assert db.scalar(select(func.count()).select_from(Client)) == 8
    assert db.scalar(select(func.count()).select_from(Vehicule)) == 8
    peugeot = db.scalars(select(Vehicule).where(Vehicule.immatriculation == "GH-482-KL")).one()
    assert (peugeot.marque, peugeot.modele, peugeot.kilometrage) == ("Peugeot", "308 SW", 84312)
    assert peugeot.vin == "VF3LCYHZPKS123456"
    assert peugeot.date_mise_en_circulation == date(2019, 3, 1)
    assert (peugeot.client.prenom, peugeot.client.nom) == ("Claire", "Laurent")
    assert peugeot.client.email is not None and peugeot.client.email.endswith("@exemple.test")
