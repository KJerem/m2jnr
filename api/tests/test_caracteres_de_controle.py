"""Revue du sprint 3 — caractères de contrôle dans les textes saisis.

PostgreSQL refuse le caractère NUL dans un champ texte : « a\\u0000b » dans une désignation de
devis ou un nom de client faisait une erreur 500. Les textes libres refusent désormais NUL et
les autres caractères de contrôle (422 « Caractère non autorisé. » sur le champ) ; la
tabulation et les retours à la ligne restent permis.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.models import Utilisateur
from app.schemas.client import ClientEntree
from app.schemas.commun import MESSAGE_CARACTERE_INTERDIT
from app.schemas.devis import LigneEntree
from app.schemas.ordre import OrdreEntree, OrdreModification
from app.schemas.rendez_vous import RendezVousEntree
from app.schemas.vehicule import VehiculeEntree

CLIENT = {"nom": "Martin", "prenom": "Léa", "telephone": "0612345678"}
VEHICULE = {"immatriculation": "GH-482-KL", "marque": "Peugeot", "modele": "308", "kilometrage": 1}
ORDRE = {
    "vehicule_id": 1,
    "demande_client": "Bruit au freinage.",
    "diagnostic": "Plaquettes usées.",
    "taches": [{"libelle": "Remplacer les plaquettes", "duree_prevue_minutes": 30}],
}
RENDEZ_VOUS = {
    "vehicule_id": 1,
    "pont_id": 1,
    "debut": "2026-11-19T09:00",
    "duree_minutes": 60,
    "motif": "Révision",
}
LIGNE = {
    "type": "piece",
    "reference": "PLQ-308",
    "designation": "Plaquettes",
    "quantite": "1",
    "prix_unitaire_ht_centimes": 4850,
}

CHAMPS_TEXTE: list[tuple[type[BaseModel], dict[str, Any], tuple[str | int, ...]]] = [
    (ClientEntree, CLIENT, ("nom",)),
    (ClientEntree, CLIENT, ("prenom",)),
    (VehiculeEntree, VEHICULE, ("marque",)),
    (VehiculeEntree, VEHICULE, ("modele",)),
    (OrdreEntree, ORDRE, ("demande_client",)),
    (OrdreEntree, ORDRE, ("diagnostic",)),
    (OrdreEntree, ORDRE, ("taches", 0, "libelle")),
    (OrdreModification, ORDRE, ("demande_client",)),
    (RendezVousEntree, RENDEZ_VOUS, ("motif",)),
    (LigneEntree, LIGNE, ("designation",)),
    (LigneEntree, LIGNE, ("reference",)),
]


def _avec(donnees: dict[str, Any], chemin: tuple[str | int, ...], valeur: str) -> dict[str, Any]:
    copie: Any = {
        cle: [dict(t) for t in v] if isinstance(v, list) else v for cle, v in donnees.items()
    }
    cible = copie
    for etape in chemin[:-1]:
        cible = cible[etape]
    cible[chemin[-1]] = valeur
    return dict(copie)


@pytest.mark.parametrize("caractere", ["\x00", "\x07", "\x1b", "\x7f", "\x85"])
@pytest.mark.parametrize(("schema", "donnees", "chemin"), CHAMPS_TEXTE)
def test_texte_libre_refuse_les_caracteres_de_controle(
    schema: type[BaseModel],
    donnees: dict[str, Any],
    chemin: tuple[str | int, ...],
    caractere: str,
) -> None:
    schema.model_validate(donnees)  # la base est valide

    with pytest.raises(ValidationError) as erreur:
        schema.model_validate(_avec(donnees, chemin, f"a{caractere}b"))

    erreurs = erreur.value.errors()
    assert [e["loc"] for e in erreurs] == [chemin]
    assert MESSAGE_CARACTERE_INTERDIT in erreurs[0]["msg"]


def test_tabulation_et_retours_a_la_ligne_restent_permis() -> None:
    ordre = OrdreEntree.model_validate(
        {**ORDRE, "demande_client": "Bruit au freinage.\r\nVibrations\tà 90 km/h."}
    )

    assert ordre.demande_client == "Bruit au freinage.\r\nVibrations\tà 90 km/h."


@pytest.mark.parametrize("champ", ["designation", "reference"])
def test_devis_nul_dans_une_ligne_422_et_non_500(client_gerant: TestClient, champ: str) -> None:
    client = client_gerant.post("/clients", json=CLIENT).json()
    vehicule = client_gerant.post(f"/clients/{client['id']}/vehicules", json=VEHICULE).json()
    ordre = client_gerant.post(
        "/ordres", json={"vehicule_id": vehicule["id"], "demande_client": "Freins"}
    ).json()

    reponse = client_gerant.post(
        f"/ordres/{ordre['id']}/devis", json={"lignes": [{**LIGNE, champ: "a\u0000b"}]}
    )

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {f"lignes.0.{champ}": MESSAGE_CARACTERE_INTERDIT}


def test_fiche_client_nul_422_et_non_500(client_gerant: TestClient) -> None:
    reponse = client_gerant.post("/clients", json={**CLIENT, "nom": "Martin\u0000"})

    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"nom": MESSAGE_CARACTERE_INTERDIT}


def test_connexion_avec_nul_dans_l_email_401_et_non_500(
    client_anonyme: TestClient, gerant: Utilisateur
) -> None:
    reponse = client_anonyme.post(
        "/auth/login", json={"email": f"{gerant.email}\u0000", "mot_de_passe": "x"}
    )

    assert reponse.status_code == 401
    assert reponse.json()["message"] == "Identifiants invalides."
