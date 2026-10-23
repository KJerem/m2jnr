"""Table utilisateur : e-mail unique (citext), mot de passe haché, rôle, blocage.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

role_utilisateur = postgresql.ENUM("gerant", "mecanicien", name="role_utilisateur", create_type=False)


def upgrade() -> None:
    role_utilisateur.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "utilisateur",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("nom", sa.String(100), nullable=False),
        sa.Column("mot_de_passe_hash", sa.String(255), nullable=False),
        sa.Column("role", role_utilisateur, nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tentatives_echouees", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("bloque_jusqu_a", sa.DateTime(timezone=True), nullable=True),
        sa.Column("derniere_connexion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_utilisateur"),
        sa.UniqueConstraint("email", name="uq_utilisateur_email"),
        sa.CheckConstraint("tentatives_echouees >= 0", name="ck_utilisateur_tentatives_positives"),
    )


def downgrade() -> None:
    op.drop_table("utilisateur")
    role_utilisateur.drop(op.get_bind(), checkfirst=True)
