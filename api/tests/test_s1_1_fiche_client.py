"""Story S1.1 — fiche client : champs obligatoires, téléphone, doublon, pagination, accès."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.services.telephone import (
    MESSAGE_TELEPHONE_INVALIDE,
    formater_telephone,
    normaliser_telephone,
)


def _client(**surcharges: Any) -> dict[str, Any]:
    corps: dict[str, Any] = {
        "nom": "Laurent",
        "prenom": "Claire",
        "telephone": "06 12 34 56 78",
        "email": "claire.laurent@exemple.test",
        "consentement_rappels": False,
    }
    corps.update(surcharges)
    return corps


# --- Normalisation du téléphone (fonctions pures) ------------------------------------------


@pytest.mark.parametrize(
    "saisie",
    [
        "06 12 34 56 78",
        "06.12.34.56.78",
        "06-12-34-56-78",
        "0612345678",
        "+33 6 12 34 56 78",
        "+33612345678",
        "0033612345678",
        "0033 6 12 34 56 78",
        "  06 12 34 56 78  ",
    ],
)
def test_normalisation_des_variantes_de_telephone(saisie: str) -> None:
    assert normaliser_telephone(saisie) == "0612345678"


@pytest.mark.parametrize(
    "saisie",
    ["", "12345", "061234567", "06123456789", "0012345678", "+44 7911 123456", "06 12 AB 56 78"],
)
def test_telephone_invalide(saisie: str) -> None:
    with pytest.raises(ValueError, match=MESSAGE_TELEPHONE_INVALIDE):
        normaliser_telephone(saisie)


def test_formatage_du_telephone() -> None:
    assert formater_telephone("0612345678") == "06 12 34 56 78"


# --- Création -------------------------------------------------------------------------------


def test_creation_d_un_client(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients", json=_client(telephone="+33 6 12 34 56 78"))

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["telephone"] == "0612345678"
    assert corps["nom"] == "Laurent"
    assert corps["email"] == "claire.laurent@exemple.test"
    assert corps["consentement_rappels"] is False
    assert corps["nombre_vehicules"] == 0
    assert client_gerant.get(f"/clients/{corps['id']}").json() == corps


def test_consentement_aux_rappels_faux_par_defaut(client_gerant: TestClient) -> None:
    corps = _client()
    del corps["consentement_rappels"]

    assert client_gerant.post("/clients", json=corps).json()["consentement_rappels"] is False


def test_champs_facultatifs_vides_enregistres_comme_non_renseignes(
    client_gerant: TestClient,
) -> None:
    reponse = client_gerant.post("/clients", json=_client(prenom="  ", email=""))

    assert reponse.status_code == 201
    assert reponse.json()["prenom"] is None
    assert reponse.json()["email"] is None


@pytest.mark.parametrize("champ", ["nom", "telephone"])
def test_champ_obligatoire_manquant(client_gerant: TestClient, champ: str) -> None:
    corps = _client()
    del corps[champ]

    reponse = client_gerant.post("/clients", json=corps)

    assert reponse.status_code == 422
    assert reponse.json()["code"] == "validation"
    assert reponse.json()["champs"] == {champ: "Champ obligatoire."}


def test_nom_et_telephone_vides(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients", json=_client(nom="   ", telephone=""))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {
        "nom": "Champ obligatoire.",
        "telephone": "Champ obligatoire.",
    }


def test_telephone_invalide_refuse(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients", json=_client(telephone="12 34"))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"telephone": "Numéro de téléphone français invalide."}


def test_email_invalide_refuse(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients", json=_client(email="claire@"))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"email": "Adresse e-mail invalide."}


def test_nom_trop_long(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients", json=_client(nom="x" * 101))

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"nom": "100 caractères maximum."}


# --- Doublon de téléphone -------------------------------------------------------------------


def test_doublon_de_telephone_puis_confirmation(client_gerant: TestClient) -> None:
    premier = client_gerant.post("/clients", json=_client()).json()

    doublon = client_gerant.post(
        "/clients", json=_client(nom="Laurent", prenom="Marc", telephone="06.12.34.56.78")
    )

    assert doublon.status_code == 409
    assert doublon.json() == {
        "code": "doublon_telephone",
        "message": "Un client avec ce téléphone existe déjà.",
        "champs": {},
        "clients": [{"id": premier["id"], "nom": "Laurent", "prenom": "Claire"}],
    }
    confirme = client_gerant.post(
        "/clients?confirmer_doublon=true", json=_client(prenom="Marc", telephone="0612345678")
    )
    assert confirme.status_code == 201
    assert confirme.json()["telephone"] == "0612345678"


def test_modification_soumise_a_la_meme_regle_de_doublon(client_gerant: TestClient) -> None:
    claire = client_gerant.post("/clients", json=_client()).json()
    marc = client_gerant.post(
        "/clients", json=_client(prenom="Marc", telephone="07 00 00 00 01")
    ).json()

    # Garder son propre numéro n'est pas un doublon.
    soi_meme = client_gerant.put(f"/clients/{claire['id']}", json=_client(nom="Laurent-Petit"))
    assert soi_meme.status_code == 200
    assert soi_meme.json()["nom"] == "Laurent-Petit"

    doublon = client_gerant.put(f"/clients/{marc['id']}", json=_client(prenom="Marc"))
    assert doublon.status_code == 409
    assert doublon.json()["clients"] == [
        {"id": claire["id"], "nom": "Laurent-Petit", "prenom": "Claire"}
    ]

    confirme = client_gerant.put(
        f"/clients/{marc['id']}?confirmer_doublon=true", json=_client(prenom="Marc")
    )
    assert confirme.status_code == 200
    assert confirme.json()["telephone"] == "0612345678"


# --- Modification et consultation -----------------------------------------------------------


def test_modification_d_un_client(client_gerant: TestClient) -> None:
    cree = client_gerant.post("/clients", json=_client()).json()

    reponse = client_gerant.put(
        f"/clients/{cree['id']}",
        json=_client(email=None, consentement_rappels=True, telephone="0033612345678"),
    )

    assert reponse.status_code == 200
    assert reponse.json()["email"] is None
    assert reponse.json()["consentement_rappels"] is True


def test_modification_valide_les_champs(client_gerant: TestClient) -> None:
    cree = client_gerant.post("/clients", json=_client()).json()

    reponse = client_gerant.put(f"/clients/{cree['id']}", json=_client(telephone="abc"))

    assert reponse.status_code == 422
    assert "telephone" in reponse.json()["champs"]


def test_client_inconnu_404(client_gerant: TestClient) -> None:
    assert client_gerant.get("/clients/999999").status_code == 404
    assert client_gerant.put("/clients/999999", json=_client()).status_code == 404


# --- Liste paginée --------------------------------------------------------------------------


def test_liste_paginee_triee_par_nom_puis_prenom(client_gerant: TestClient) -> None:
    noms = [("Petit", "Jean"), ("diallo", "Awa"), ("Laurent", "Marc"), ("Laurent", "Claire")]
    for i, (nom, prenom) in enumerate(noms):
        corps = _client(nom=nom, prenom=prenom, telephone=f"06 00 00 00 0{i}")
        assert client_gerant.post("/clients", json=corps).status_code == 201

    page1 = client_gerant.get("/clients?page=1&taille=3").json()
    page2 = client_gerant.get("/clients?page=2&taille=3").json()

    assert (page1["total"], page1["page"], page1["taille"]) == (4, 1, 3)
    assert [(c["nom"], c["prenom"]) for c in page1["elements"]] == [
        ("diallo", "Awa"),
        ("Laurent", "Claire"),
        ("Laurent", "Marc"),
    ]
    assert [c["nom"] for c in page2["elements"]] == ["Petit"]
    assert client_gerant.get("/clients?page=3&taille=3").json()["elements"] == []


def test_pagination_par_defaut_et_bornes(client_gerant: TestClient) -> None:
    defaut = client_gerant.get("/clients").json()
    assert (defaut["page"], defaut["taille"], defaut["total"]) == (1, 20, 0)

    assert client_gerant.get("/clients?page=0").status_code == 422
    assert client_gerant.get("/clients?taille=101").status_code == 422


# --- Accès ----------------------------------------------------------------------------------


def test_mecanicien_refuse_sur_les_clients(client_mecanicien: TestClient) -> None:
    assert client_mecanicien.get("/clients").status_code == 403
    assert client_mecanicien.post("/clients", json=_client()).status_code == 403
    assert client_mecanicien.get("/clients/1").status_code == 403
    assert client_mecanicien.put("/clients/1", json=_client()).status_code == 403


def test_sans_session_401(client_anonyme: TestClient) -> None:
    assert client_anonyme.get("/clients").status_code == 401
    assert client_anonyme.post("/clients", json=_client()).status_code == 401
