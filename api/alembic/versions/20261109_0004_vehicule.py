"""Table vehicule : rattachée à un client, immatriculation SIV unique, kilométrage ≥ 0.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("immatriculation", sa.String(9), nullable=False),
        sa.Column("marque", sa.String(50), nullable=False),
        sa.Column("modele", sa.String(80), nullable=False),
        sa.Column("kilometrage", sa.Integer(), nullable=False),
        sa.Column("vin", sa.String(17), nullable=True),
        sa.Column("date_mise_en_circulation", sa.Date(), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vehicule"),
        sa.ForeignKeyConstraint(
            ["client_id"], ["client.id"], name="fk_vehicule_client_id_client", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("immatriculation", name="uq_vehicule_immatriculation"),
        sa.CheckConstraint(
            "immatriculation ~ '^[A-HJ-NP-TV-Z]{2}-[0-9]{3}-[A-HJ-NP-TV-Z]{2}$' "
            "AND substr(immatriculation, 4, 3) <> '000'",
            name="ck_vehicule_immatriculation_siv",
        ),
        sa.CheckConstraint("kilometrage >= 0", name="ck_vehicule_kilometrage_positif"),
        sa.CheckConstraint("vin IS NULL OR vin ~ '^[A-HJ-NPR-Z0-9]{17}$'", name="ck_vehicule_vin_format"),
        sa.CheckConstraint("char_length(btrim(marque)) > 0", name="ck_vehicule_marque_non_vide"),
        sa.CheckConstraint("char_length(btrim(modele)) > 0", name="ck_vehicule_modele_non_vide"),
    )
    op.create_index("ix_vehicule_client_id", "vehicule", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_vehicule_client_id", table_name="vehicule")
    op.drop_table("vehicule")
