"""Story S1.4 — interventions d'un véhicule, de la plus récente à la plus ancienne."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Client, OrdreTravail, StatutOT, TacheOT, Utilisateur, Vehicule


def _vehicule(db: Session, plaque: str = "GH-482-KL") -> Vehicule:
    client = Client(nom="Laurent", prenom="Claire", telephone="0612483075")
    db.add(client)
    db.flush()
    vehicule = Vehicule(
        client_id=client.id,
        immatriculation=plaque,
        marque="Peugeot",
        modele="308 SW",
        kilometrage=84312,
    )
    db.add(vehicule)
    db.flush()
    return vehicule


def _ordre(
    db: Session,
    vehicule: Vehicule,
    auteur: Utilisateur,
    numero: str,
    ouvert_le: datetime,
    **champs: object,
) -> OrdreTravail:
    ordre = OrdreTravail(
        numero=numero,
        vehicule_id=vehicule.id,
        demande_client=f"Demande {numero}",
        ouvert_le=ouvert_le,
        cree_par=auteur.id,
        **champs,
    )
    db.add(ordre)
    db.flush()
    return ordre


@pytest.fixture
def vehicule(db: Session) -> Vehicule:
    return _vehicule(db)


def test_interventions_de_la_plus_recente_a_la_plus_ancienne(
    client_mecanicien: TestClient,
    vehicule: Vehicule,
    gerant: Utilisateur,
    mecanicien: Utilisateur,
    db: Session,
) -> None:
    ancienne = _ordre(
        db,
        vehicule,
        gerant,
        "OT-2025-014",
        datetime(2025, 10, 14, 7, 30, tzinfo=UTC),
        statut=StatutOT.LIVRE,
        cloture_le=datetime(2025, 10, 14, 16, 0, tzinfo=UTC),
        kilometrage_entree=75120,
        diagnostic="Rien à signaler.",
        mecanicien_id=mecanicien.id,
    )
    ancienne.taches = [
        TacheOT(
            libelle="Vidange",
            duree_prevue_minutes=30,
            terminee=True,
            terminee_le=datetime(2025, 10, 14, 9, 0, tzinfo=UTC),
            terminee_par=mecanicien.id,
        )
    ]
    recente = _ordre(db, vehicule, gerant, "OT-2026-003", datetime(2026, 11, 16, 8, 10, tzinfo=UTC))
    recente.taches = [TacheOT(libelle="Plaquettes", duree_prevue_minutes=90, position=0)]
    _ordre(
        db,
        vehicule,
        gerant,
        "OT-2026-001",
        datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        statut=StatutOT.LIVRE,
    )
    # Même heure d'ouverture : le plus grand identifiant (le plus récent créé) d'abord.
    _ordre(db, vehicule, gerant, "OT-2026-004", datetime(2026, 11, 16, 8, 10, tzinfo=UTC))
    autre_vehicule = _vehicule(db, "EK-730-PA")
    _ordre(db, autre_vehicule, gerant, "OT-2026-002", datetime(2026, 5, 1, 9, 0, tzinfo=UTC))
    db.flush()

    reponse = client_mecanicien.get(f"/vehicules/{vehicule.id}/historique")

    assert reponse.status_code == 200
    historique = reponse.json()
    assert [i["numero"] for i in historique] == [
        "OT-2026-004",
        "OT-2026-003",
        "OT-2026-001",
        "OT-2025-014",
    ]
    assert historique[-1] == {
        "id": ancienne.id,
        "numero": "OT-2025-014",
        "statut": "livre",
        "demande_client": "Demande OT-2025-014",
        "diagnostic": "Rien à signaler.",
        "kilometrage_entree": 75120,
        "ouvert_le": "2025-10-14T07:30:00Z",
        "cloture_le": "2025-10-14T16:00:00Z",
        "mecanicien": {"id": mecanicien.id, "nom": "Karim B."},
        "taches": [{"libelle": "Vidange", "terminee": True}],
    }
    assert historique[1]["taches"] == [{"libelle": "Plaquettes", "terminee": False}]
    assert historique[1]["mecanicien"] is None
    assert "0612483075" not in reponse.text


def test_historique_vide(client_gerant: TestClient, vehicule: Vehicule) -> None:
    reponse = client_gerant.get(f"/vehicules/{vehicule.id}/historique")

    assert reponse.status_code == 200
    assert reponse.json() == []


@pytest.mark.parametrize("identifiant", ["999999", "2147483648", "0"])
def test_vehicule_inconnu_404(client_mecanicien: TestClient, identifiant: str) -> None:
    reponse = client_mecanicien.get(f"/vehicules/{identifiant}/historique")

    assert reponse.status_code == 404
    assert reponse.json()["message"] == "Véhicule introuvable."


def test_ordre_ouvert_par_l_api_visible_dans_l_historique(
    client_gerant: TestClient, client_mecanicien: TestClient, vehicule: Vehicule
) -> None:
    ordre = client_gerant.post(
        "/ordres", json={"vehicule_id": vehicule.id, "demande_client": "Bruit au freinage."}
    ).json()

    historique = client_mecanicien.get(f"/vehicules/{vehicule.id}/historique").json()

    assert [(i["id"], i["statut"]) for i in historique] == [(ordre["id"], "a_faire")]


def test_sans_session_401(client_anonyme: TestClient, vehicule: Vehicule) -> None:
    assert client_anonyme.get(f"/vehicules/{vehicule.id}/historique").status_code == 401
