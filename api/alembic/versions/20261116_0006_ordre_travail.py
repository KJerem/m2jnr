"""Ordres de travail, tâches prévues et compteurs de numérotation.

- ordre_travail : numéro unique « OT-AAAA-nnn », véhicule obligatoire, mécanicien facultatif,
  demande du client, diagnostic, statut (enum statut_ot), priorité, kilométrage d'entrée,
  restitution prévue, dates d'ouverture et de clôture, auteur ;
- tache_ot : tâches de l'OT (supprimées avec lui), durée prévue > 0, ordre d'affichage, fin ;
- compteur : dernier numéro attribué par type de document et par année (sans trou).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

statut_ot = postgresql.ENUM(
    "a_faire", "en_cours", "termine", "livre", name="statut_ot", create_type=False
)


def _horodatage() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    statut_ot.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "compteur",
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("annee", sa.Integer(), nullable=False),
        sa.Column("dernier", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("type", "annee", name="pk_compteur"),
        sa.CheckConstraint("dernier >= 0", name=op.f("ck_compteur_dernier_positif")),
    )

    op.create_table(
        "ordre_travail",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("vehicule_id", sa.Integer(), nullable=False),
        sa.Column("mecanicien_id", sa.Integer(), nullable=True),
        sa.Column("demande_client", sa.Text(), nullable=False),
        sa.Column("diagnostic", sa.Text(), nullable=True),
        sa.Column("statut", statut_ot, nullable=False, server_default="a_faire"),
        sa.Column("prioritaire", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("kilometrage_entree", sa.Integer(), nullable=True),
        sa.Column("restitution_prevue", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ouvert_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cloture_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cree_par", sa.Integer(), nullable=False),
        *_horodatage(),
        sa.PrimaryKeyConstraint("id", name="pk_ordre_travail"),
        sa.UniqueConstraint("numero", name="uq_ordre_travail_numero"),
        sa.ForeignKeyConstraint(
            ["vehicule_id"], ["vehicule.id"],
            name="fk_ordre_travail_vehicule_id_vehicule", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mecanicien_id"], ["utilisateur.id"],
            name="fk_ordre_travail_mecanicien_id_utilisateur", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cree_par"], ["utilisateur.id"],
            name="fk_ordre_travail_cree_par_utilisateur", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "numero ~ '^OT-[0-9]{4}-[0-9]{3,}$'", name=op.f("ck_ordre_travail_numero_format")
        ),
        sa.CheckConstraint(
            "char_length(btrim(demande_client)) > 0", name=op.f("ck_ordre_travail_demande_non_vide")
        ),
        sa.CheckConstraint(
            "kilometrage_entree IS NULL OR kilometrage_entree >= 0",
            name=op.f("ck_ordre_travail_kilometrage_entree_positif"),
        ),
        sa.CheckConstraint(
            "cloture_le IS NULL OR cloture_le >= ouvert_le",
            name=op.f("ck_ordre_travail_cloture_apres_ouverture"),
        ),
    )
    op.create_index("ix_ordre_travail_vehicule_id", "ordre_travail", ["vehicule_id"])
    op.create_index("ix_ordre_travail_mecanicien_id", "ordre_travail", ["mecanicien_id"])
    op.create_index("ix_ordre_travail_statut", "ordre_travail", ["statut"])

    op.create_table(
        "tache_ot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ordre_travail_id", sa.Integer(), nullable=False),
        sa.Column("libelle", sa.String(200), nullable=False),
        sa.Column("duree_prevue_minutes", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("terminee", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("terminee_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminee_par", sa.Integer(), nullable=True),
        *_horodatage(),
        sa.PrimaryKeyConstraint("id", name="pk_tache_ot"),
        sa.ForeignKeyConstraint(
            ["ordre_travail_id"], ["ordre_travail.id"],
            name="fk_tache_ot_ordre_travail_id_ordre_travail", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["terminee_par"], ["utilisateur.id"],
            name="fk_tache_ot_terminee_par_utilisateur", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("char_length(btrim(libelle)) > 0", name=op.f("ck_tache_ot_libelle_non_vide")),
        sa.CheckConstraint("duree_prevue_minutes > 0", name=op.f("ck_tache_ot_duree_positive")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_tache_ot_position_positive")),
        sa.CheckConstraint(
            "(terminee AND terminee_le IS NOT NULL)"
            " OR (NOT terminee AND terminee_le IS NULL AND terminee_par IS NULL)",
            name=op.f("ck_tache_ot_fin_coherente"),
        ),
    )
    op.create_index("ix_tache_ot_ordre_travail_id", "tache_ot", ["ordre_travail_id"])


def downgrade() -> None:
    op.drop_index("ix_tache_ot_ordre_travail_id", table_name="tache_ot")
    op.drop_table("tache_ot")
    op.drop_index("ix_ordre_travail_statut", table_name="ordre_travail")
    op.drop_index("ix_ordre_travail_mecanicien_id", table_name="ordre_travail")
    op.drop_index("ix_ordre_travail_vehicule_id", table_name="ordre_travail")
    op.drop_table("ordre_travail")
    op.drop_table("compteur")
    statut_ot.drop(op.get_bind(), checkfirst=True)
