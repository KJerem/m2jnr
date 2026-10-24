"""Ponts, rendez-vous et lien entre un rendez-vous et son ordre de travail.

- pont : nom unique, actif ; trois ponts créés (Pont 1, Pont 2, Pont 3) ;
- rendez_vous : véhicule, pont, début, durée (1 à 600 min), fin calculée par la base,
  motif ; contrainte EXCLUDE (btree_gist, installée par la migration 0001) : deux créneaux
  [début, fin[ d'un même pont ne se chevauchent jamais ;
- ordre_travail.rendez_vous_id : rendez-vous d'origine, au plus un OT par rendez-vous.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPRESSION_FIN = (
    "((debut AT TIME ZONE 'UTC') + duree_minutes * interval '1 minute') AT TIME ZONE 'UTC'"
)


def _horodatage() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    pont = op.create_table(
        "pont",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nom", sa.String(50), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_horodatage(),
        sa.PrimaryKeyConstraint("id", name="pk_pont"),
        sa.UniqueConstraint("nom", name="uq_pont_nom"),
        sa.CheckConstraint("char_length(btrim(nom)) > 0", name=op.f("ck_pont_nom_non_vide")),
    )
    op.bulk_insert(pont, [{"nom": "Pont 1"}, {"nom": "Pont 2"}, {"nom": "Pont 3"}])

    op.create_table(
        "rendez_vous",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vehicule_id", sa.Integer(), nullable=False),
        sa.Column("pont_id", sa.Integer(), nullable=False),
        sa.Column("debut", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duree_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "fin", sa.DateTime(timezone=True), sa.Computed(EXPRESSION_FIN, persisted=True)
        ),
        sa.Column("motif", sa.Text(), nullable=False),
        sa.Column("cree_par", sa.Integer(), nullable=False),
        *_horodatage(),
        sa.PrimaryKeyConstraint("id", name="pk_rendez_vous"),
        sa.ForeignKeyConstraint(
            ["vehicule_id"], ["vehicule.id"],
            name="fk_rendez_vous_vehicule_id_vehicule", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pont_id"], ["pont.id"], name="fk_rendez_vous_pont_id_pont", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cree_par"], ["utilisateur.id"],
            name="fk_rendez_vous_cree_par_utilisateur", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "duree_minutes > 0 AND duree_minutes <= 600", name=op.f("ck_rendez_vous_duree_bornee")
        ),
        sa.CheckConstraint(
            "char_length(btrim(motif)) > 0", name=op.f("ck_rendez_vous_motif_non_vide")
        ),
        postgresql.ExcludeConstraint(
            ("pont_id", "="),
            (sa.literal_column("tstzrange(debut, fin, '[)')"), "&&"),
            name="excl_rendez_vous_pont_creneau",
            using="gist",
        ),
    )
    op.create_index("ix_rendez_vous_vehicule_id", "rendez_vous", ["vehicule_id"])
    op.create_index("ix_rendez_vous_pont_id", "rendez_vous", ["pont_id"])
    op.create_index("ix_rendez_vous_debut", "rendez_vous", ["debut"])

    op.add_column("ordre_travail", sa.Column("rendez_vous_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ordre_travail_rendez_vous_id_rendez_vous",
        "ordre_travail", "rendez_vous", ["rendez_vous_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_ordre_travail_rendez_vous_id", "ordre_travail", ["rendez_vous_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_ordre_travail_rendez_vous_id", "ordre_travail", type_="unique")
    op.drop_constraint(
        "fk_ordre_travail_rendez_vous_id_rendez_vous", "ordre_travail", type_="foreignkey"
    )
    op.drop_column("ordre_travail", "rendez_vous_id")
    op.drop_index("ix_rendez_vous_debut", table_name="rendez_vous")
    op.drop_index("ix_rendez_vous_pont_id", table_name="rendez_vous")
    op.drop_index("ix_rendez_vous_vehicule_id", table_name="rendez_vous")
    op.drop_table("rendez_vous")
    op.drop_table("pont")
