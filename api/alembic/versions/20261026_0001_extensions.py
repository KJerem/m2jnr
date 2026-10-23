"""Extensions PostgreSQL utilisées par le modèle.

- citext : e-mails insensibles à la casse
- btree_gist : contrainte d'exclusion des rendez-vous qui se chevauchent sur un pont
- pg_trgm : recherche approchée (nom, téléphone, immatriculation)

Revision ID: 0001
Revises:
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
    op.execute("DROP EXTENSION IF EXISTS citext")
