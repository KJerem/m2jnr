"""Devis et lignes de devis (story S4.1).

- devis : ordre de travail chiffré (plusieurs devis possibles par OT, le courant est le plus
  récent), taux de TVA en points de base (2000 = 20 %), totaux HT, TVA et TTC en centimes
  (bigint) calculés par l'application et enregistrés, auteur, horodatages ;
- ligne_devis : type (enum type_ligne : piece | main_oeuvre), référence facultative,
  désignation, quantité numeric(10,2) > 0, prix unitaire HT en centimes ≥ 0, total HT de la
  ligne, ordre d'affichage ; supprimées avec leur devis.

La colonne `statut` du devis (brouillon, envoyé, accepté, refusé) n'est pas créée ici : elle
appartient à la story S4.2 (sprint 4), qui l'ajoutera par une migration dédiée.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

type_ligne = postgresql.ENUM("piece", "main_oeuvre", name="type_ligne", create_type=False)


def upgrade() -> None:
    type_ligne.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "devis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ordre_travail_id", sa.Integer(), nullable=False),
        sa.Column("taux_tva_bp", sa.Integer(), nullable=False, server_default=sa.text("2000")),
        sa.Column("total_ht_centimes", sa.BigInteger(), nullable=False),
        sa.Column("total_tva_centimes", sa.BigInteger(), nullable=False),
        sa.Column("total_ttc_centimes", sa.BigInteger(), nullable=False),
        sa.Column("cree_par", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_devis"),
        sa.ForeignKeyConstraint(
            ["ordre_travail_id"], ["ordre_travail.id"],
            name="fk_devis_ordre_travail_id_ordre_travail", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cree_par"], ["utilisateur.id"],
            name="fk_devis_cree_par_utilisateur", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "taux_tva_bp >= 0 AND taux_tva_bp <= 10000", name=op.f("ck_devis_taux_tva_borne")
        ),
        sa.CheckConstraint("total_ht_centimes >= 0", name=op.f("ck_devis_total_ht_positif")),
        sa.CheckConstraint("total_tva_centimes >= 0", name=op.f("ck_devis_total_tva_positif")),
        sa.CheckConstraint("total_ttc_centimes >= 0", name=op.f("ck_devis_total_ttc_positif")),
        sa.CheckConstraint(
            "total_ttc_centimes = total_ht_centimes + total_tva_centimes",
            name=op.f("ck_devis_ttc_coherent"),
        ),
    )
    op.create_index("ix_devis_ordre_travail_id", "devis", ["ordre_travail_id"])

    op.create_table(
        "ligne_devis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("devis_id", sa.Integer(), nullable=False),
        sa.Column("type", type_ligne, nullable=False),
        sa.Column("reference", sa.String(40), nullable=True),
        sa.Column("designation", sa.String(200), nullable=False),
        sa.Column("quantite", sa.Numeric(10, 2), nullable=False),
        sa.Column("prix_unitaire_ht_centimes", sa.BigInteger(), nullable=False),
        sa.Column("total_ht_centimes", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id", name="pk_ligne_devis"),
        sa.ForeignKeyConstraint(
            ["devis_id"], ["devis.id"], name="fk_ligne_devis_devis_id_devis", ondelete="CASCADE"
        ),
        sa.CheckConstraint("quantite > 0", name=op.f("ck_ligne_devis_quantite_positive")),
        sa.CheckConstraint(
            "prix_unitaire_ht_centimes >= 0", name=op.f("ck_ligne_devis_prix_positif")
        ),
        sa.CheckConstraint("total_ht_centimes >= 0", name=op.f("ck_ligne_devis_total_positif")),
        sa.CheckConstraint(
            "char_length(btrim(designation)) > 0",
            name=op.f("ck_ligne_devis_designation_non_vide"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_ligne_devis_position_positive")),
    )
    op.create_index("ix_ligne_devis_devis_id", "ligne_devis", ["devis_id"])


def downgrade() -> None:
    op.drop_index("ix_ligne_devis_devis_id", table_name="ligne_devis")
    op.drop_table("ligne_devis")
    op.drop_index("ix_devis_ordre_travail_id", table_name="devis")
    op.drop_table("devis")
    type_ligne.drop(op.get_bind(), checkfirst=True)
