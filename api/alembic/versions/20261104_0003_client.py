"""Table client : nom et téléphone obligatoires, téléphone normalisé et indexé, consentement.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nom", sa.String(100), nullable=False),
        sa.Column("prenom", sa.String(100), nullable=True),
        sa.Column("telephone", sa.String(10), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("consentement_rappels", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_client"),
        sa.CheckConstraint("char_length(btrim(nom)) > 0", name="ck_client_nom_non_vide"),
        sa.CheckConstraint("telephone ~ '^0[1-9][0-9]{8}$'", name="ck_client_telephone_normalise"),
    )
    op.create_index("ix_client_telephone", "client", ["telephone"])


def downgrade() -> None:
    op.drop_index("ix_client_telephone", table_name="client")
    op.drop_table("client")
