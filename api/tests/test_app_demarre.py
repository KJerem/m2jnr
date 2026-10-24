"""Sprint 0 — tâche 0.8 : l'application démarre et joint la base."""

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.types import Message, Receive, Scope, Send

from app.db import get_db
from app.models import Utilisateur
from tests.conftest import connecter, preparer_csrf


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


# --- Transaction validée avant la réponse (revue du sprint 1) ------------------------------


def test_transaction_validee_avant_l_envoi_de_la_reponse(
    app: FastAPI, db: Session, gerant: Utilisateur
) -> None:
    """Le commit de la session doit précéder l'envoi du statut : un 201 ne doit jamais être
    renvoyé pour une donnée qui n'est pas encore en base. La dépendance d'authentification et
    la route partagent une seule session."""
    evenements: list[str] = []

    def _get_db() -> Iterator[Session]:
        evenements.append("session")
        yield db
        db.flush()
        evenements.append("commit")

    app.dependency_overrides[get_db] = _get_db

    async def application_espionnee(scope: Scope, receive: Receive, send: Send) -> None:
        async def envoyer(message: Message) -> None:
            if message["type"] == "http.response.start":
                evenements.append("réponse")
            await send(message)

        await app(scope, receive, envoyer)

    with TestClient(application_espionnee, base_url="http://testserver") as c:
        preparer_csrf(c)
        connecter(c, gerant.email)
        evenements.clear()

        reponse = c.post("/clients", json={"nom": "Laurent", "telephone": "06 12 34 56 78"})

    assert reponse.status_code == 201
    assert evenements == ["session", "commit", "réponse"]
