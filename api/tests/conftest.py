"""Fixtures pytest.

Les tests tournent sur la base PostgreSQL dédiée (TEST_DATABASE_URL, service db-test), jamais
sur la base de développement. Le schéma est créé une fois par les migrations Alembic, puis chaque
test s'exécute dans une transaction annulée à la fin : les tests sont isolés et rejouables.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app

API_DIR = Path(__file__).resolve().parent.parent


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
def app(db: Session):  # type: ignore[no-untyped-def]
    application = create_app()

    def _get_db() -> Iterator[Session]:
        yield db
        db.flush()

    application.dependency_overrides[get_db] = _get_db
    return application


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with TestClient(app, base_url="http://testserver") as c:
        yield c
