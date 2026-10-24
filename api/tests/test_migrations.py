"""Migrations Alembic : aller-retour complet, avec la convention de nommage de l'application.

`alembic downgrade` passe par env.py, qui donne `Base.metadata` (et donc sa convention de
nommage) au contexte de migration : un nom de contrainte écrit sans `op.f` y est préfixé une
seconde fois (« ck_devis_ck_devis_statut_coherent »). Les tests de migration qui configuraient
un contexte nu ne le voyaient pas (revue du sprint 4, migration 0012).

Toutes les migrations sont défaites puis rejouées dans une transaction annulée (le DDL de
PostgreSQL est transactionnel) : la base de test reste intacte.
"""

import importlib.util
from itertools import pairwise
from pathlib import Path
from types import ModuleType

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Engine, inspect, text

from app.db import Base

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _migrations() -> list[ModuleType]:
    modules = []
    for chemin in sorted(VERSIONS.glob("*.py")):
        spec = importlib.util.spec_from_file_location(chemin.stem, chemin)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


def test_les_migrations_sont_chainees_dans_l_ordre_des_fichiers() -> None:
    modules = _migrations()
    assert modules[0].down_revision is None
    for precedente, suivante in pairwise(modules):
        assert suivante.down_revision == precedente.revision


def test_aller_retour_de_toutes_les_migrations(engine: Engine) -> None:
    modules = _migrations()
    with engine.connect() as connexion:
        transaction = connexion.begin()
        try:
            contexte = MigrationContext.configure(
                connexion, opts={"target_metadata": Base.metadata}
            )
            with Operations.context(contexte):
                for module in reversed(modules):
                    module.downgrade()
                restantes = set(inspect(connexion).get_table_names()) - {"alembic_version"}
                assert restantes == set()
                for module in modules:
                    module.upgrade()
            tables = set(inspect(connexion).get_table_names())
            assert set(Base.metadata.tables) <= tables
        finally:
            transaction.rollback()
    with engine.connect() as connexion:
        assert connexion.execute(text("SELECT to_regclass('devis') IS NOT NULL")).scalar()
