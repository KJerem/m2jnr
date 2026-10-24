"""Fixtures pytest.

Les tests tournent sur la base PostgreSQL dédiée (TEST_DATABASE_URL, service db-test), jamais
sur la base de développement. Le schéma est créé une fois par les migrations Alembic, puis chaque
test s'exécute dans une transaction annulée à la fin : les tests sont isolés et rejouables.

Fixtures réutilisables :
- `make_user(role, ...)` crée un employé (mot de passe MOT_DE_PASSE_TEST par défaut) ;
- `horloge` remplace l'heure de l'application et permet d'avancer le temps ;
- `client` est un client HTTP brut (sans jeton CSRF), `client_anonyme` un client prêt pour
  le CSRF mais non connecté, `client_gerant` et `client_mecanicien` des clients connectés ;
- `nouveau_client()` fabrique un client supplémentaire (jarre de cookies indépendante).
"""

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from itertools import count
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.clock import get_now
from app.config import get_settings
from app.db import get_db
from app.main import create_app
from app.models import Role, Utilisateur
from app.security.hachage import hacher

API_DIR = Path(__file__).resolve().parent.parent

MOT_DE_PASSE_TEST = "mot-de-passe-de-test-solide"


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("TEST_DATABASE_URL manquant : pas de tests sur la base de dev.", 2)
    if url == os.environ.get("DATABASE_URL"):
        pytest.exit("TEST_DATABASE_URL doit différer de DATABASE_URL.", 2)
    return url


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _test_database_url()
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    os.environ["ALEMBIC_DATABASE_URL"] = url
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Session liée à une transaction externe annulée en fin de test.

    Les commit() du code applicatif deviennent des points de sauvegarde.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def app(db: Session) -> FastAPI:
    application = create_app()

    def _get_db() -> Iterator[Session]:
        yield db
        db.flush()

    application.dependency_overrides[get_db] = _get_db
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Client brut : aucun jeton CSRF, aucune session."""
    with TestClient(app, base_url="http://testserver") as c:
        yield c


# --- Horloge -------------------------------------------------------------------------------


class Horloge:
    """Heure contrôlée par le test, injectée à la place de app.clock.get_now."""

    def __init__(self, depart: datetime) -> None:
        self.maintenant = depart

    def avancer(self, **duree: float) -> datetime:
        self.maintenant += timedelta(**duree)
        return self.maintenant


@pytest.fixture
def horloge(app: FastAPI) -> Horloge:
    # Lundi 2 novembre 2026, 14 h 47 à Paris (13 h 47 UTC).
    h = Horloge(datetime(2026, 11, 2, 13, 47, tzinfo=UTC))
    app.dependency_overrides[get_now] = lambda: h.maintenant
    return h


# --- Utilisateurs --------------------------------------------------------------------------


@lru_cache
def _hash_par_defaut() -> str:
    # argon2id est volontairement lent : on ne hache le mot de passe de test qu'une fois.
    return hacher(MOT_DE_PASSE_TEST)


MakeUser = Callable[..., Utilisateur]


@pytest.fixture
def make_user(db: Session) -> MakeUser:
    numeros = count(1)

    def _make_user(
        role: Role | str = Role.GERANT,
        *,
        email: str | None = None,
        nom: str | None = None,
        mot_de_passe: str = MOT_DE_PASSE_TEST,
        actif: bool = True,
    ) -> Utilisateur:
        role = Role(role)
        n = next(numeros)
        utilisateur = Utilisateur(
            email=email or f"{role.value}{n}@garage.test",
            nom=nom or f"{role.value.capitalize()} {n}",
            role=role,
            mot_de_passe_hash=(
                _hash_par_defaut() if mot_de_passe == MOT_DE_PASSE_TEST else hacher(mot_de_passe)
            ),
            actif=actif,
        )
        db.add(utilisateur)
        db.flush()
        return utilisateur

    return _make_user


# --- Clients HTTP --------------------------------------------------------------------------


def preparer_csrf(c: TestClient) -> str:
    """Obtient le cookie CSRF et recopie le jeton dans l'en-tête par défaut du client."""
    jeton = c.get("/auth/csrf").json()["jeton"]
    c.headers[get_settings().csrf_header_name] = jeton
    return str(jeton)


def connecter(c: TestClient, email: str, mot_de_passe: str = MOT_DE_PASSE_TEST) -> TestClient:
    reponse = c.post("/auth/login", json={"email": email, "mot_de_passe": mot_de_passe})
    assert reponse.status_code == 200, reponse.text
    return c


@pytest.fixture
def nouveau_client(app: FastAPI) -> Iterator[Callable[[], TestClient]]:
    ouverts: list[TestClient] = []

    def _nouveau() -> TestClient:
        c = TestClient(app, base_url="http://testserver")
        c.__enter__()
        ouverts.append(c)
        preparer_csrf(c)
        return c

    yield _nouveau
    for c in ouverts:
        c.__exit__(None, None, None)


@pytest.fixture
def client_anonyme(nouveau_client: Callable[[], TestClient]) -> TestClient:
    """Client avec jeton CSRF, non connecté."""
    return nouveau_client()


@pytest.fixture
def gerant(make_user: MakeUser) -> Utilisateur:
    return make_user(Role.GERANT, email="gerant@garage.test", nom="Nadia Benali")


@pytest.fixture
def mecanicien(make_user: MakeUser) -> Utilisateur:
    return make_user(Role.MECANICIEN, email="mecanicien@garage.test", nom="Karim B.")


@pytest.fixture
def client_gerant(nouveau_client: Callable[[], TestClient], gerant: Utilisateur) -> TestClient:
    return connecter(nouveau_client(), gerant.email)


@pytest.fixture
def client_mecanicien(
    nouveau_client: Callable[[], TestClient], mecanicien: Utilisateur
) -> TestClient:
    return connecter(nouveau_client(), mecanicien.email)
