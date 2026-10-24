"""Historique des statuts des ordres de travail (horodatage et auteur de chaque changement).

Les OT déjà ouverts reçoivent leur ligne de création (ancien NULL → a_faire), datée de leur
ouverture et attribuée à leur auteur.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

statut_ot = postgresql.ENUM(
    "a_faire", "en_cours", "termine", "livre", name="statut_ot", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "historique_statut",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ordre_travail_id", sa.Integer(), nullable=False),
        sa.Column("ancien", statut_ot, nullable=True),
        sa.Column("nouveau", statut_ot, nullable=False),
        sa.Column("change_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_historique_statut"),
        sa.ForeignKeyConstraint(
            ["ordre_travail_id"], ["ordre_travail.id"],
            name="fk_historique_statut_ordre_travail_id_ordre_travail", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["utilisateur_id"], ["utilisateur.id"],
            name="fk_historique_statut_utilisateur_id_utilisateur", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "ancien IS DISTINCT FROM nouveau", name=op.f("ck_historique_statut_statut_change")
        ),
    )
    op.create_index(
        "ix_historique_statut_ordre_travail_id", "historique_statut", ["ordre_travail_id"]
    )
    op.execute(
        "INSERT INTO historique_statut (ordre_travail_id, ancien, nouveau, change_le, utilisateur_id)"
        " SELECT id, NULL, 'a_faire', ouvert_le, cree_par FROM ordre_travail ORDER BY id"
    )


def downgrade() -> None:
    op.drop_index("ix_historique_statut_ordre_travail_id", table_name="historique_statut")
    op.drop_table("historique_statut")
