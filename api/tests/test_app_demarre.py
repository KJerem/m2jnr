"""Sprint 0 — tâche 0.8 : l'application démarre et joint la base."""

from fastapi.testclient import TestClient


def test_application_demarre_et_repond(client: TestClient) -> None:
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "base": "ok"}


def test_documentation_openapi_disponible_en_developpement(client: TestClient) -> None:
    reponse = client.get("/openapi.json")
    assert reponse.status_code == 200
    assert reponse.json()["info"]["title"].startswith("Établi")


def test_route_inconnue_renvoie_une_erreur_au_format_commun(client: TestClient) -> None:
    reponse = client.get("/route-inexistante")
    assert reponse.status_code == 404
    corps = reponse.json()
    assert corps["code"] == "introuvable"
    assert corps["message"]
    assert corps["champs"] == {}
