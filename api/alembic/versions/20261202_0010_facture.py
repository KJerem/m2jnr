"""Factures, lignes de facture et immuabilité garantie par la base (story S4.3).

- facture : numéro unique « F-AAAA-nnn », devis facturé (unique : un devis au plus une fois),
  OT, date d'émission, échéance, copies figées (jsonb) du client, du véhicule et des
  mentions du garage, taux de TVA et totaux en centimes, auteur ;
- ligne_facture : lignes recopiées du devis (type_ligne de la migration 0009) ;
- trigger `refuser_modification_facture()` : UPDATE, DELETE et TRUNCATE sont refusés sur les
  deux tables (RAISE EXCEPTION 'facture immuable', SQLSTATE ET001), y compris en SQL direct.

La numérotation réutilise la table `compteur` (type 'FACTURE') : sa colonne `type` est un
varchar(20) sans liste fermée, aucune modification n'est nécessaire. Le downgrade supprime
les compteurs 'FACTURE' avec les factures (sinon, trou de numérotation au prochain upgrade).

Revision ID: 0010
Revises: 0009
Create Date: 2026-12-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

type_ligne = postgresql.ENUM("piece", "main_oeuvre", name="type_ligne", create_type=False)

FONCTION_IMMUABLE = """
CREATE FUNCTION refuser_modification_facture() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'facture immuable'
        USING ERRCODE = 'ET001',
              DETAIL = format('%s refusé sur %s : une facture émise ne se modifie pas.',
                              TG_OP, TG_TABLE_NAME);
END;
$$
"""

TABLES_IMMUABLES = ("facture", "ligne_facture")


def upgrade() -> None:
    op.create_table(
        "facture",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("devis_id", sa.Integer(), nullable=False),
        sa.Column("ordre_travail_id", sa.Integer(), nullable=False),
        sa.Column("emise_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("echeance", sa.Date(), nullable=False),
        sa.Column("client_fige", postgresql.JSONB(), nullable=False),
        sa.Column("vehicule_fige", postgresql.JSONB(), nullable=False),
        sa.Column("garage_fige", postgresql.JSONB(), nullable=False),
        sa.Column("taux_tva_bp", sa.Integer(), nullable=False),
        sa.Column("total_ht_centimes", sa.BigInteger(), nullable=False),
        sa.Column("total_tva_centimes", sa.BigInteger(), nullable=False),
        sa.Column("total_ttc_centimes", sa.BigInteger(), nullable=False),
        sa.Column("cree_par", sa.Integer(), nullable=False),
        sa.Column("cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_facture"),
        sa.UniqueConstraint("numero", name="uq_facture_numero"),
        sa.UniqueConstraint("devis_id", name="uq_facture_devis_id"),
        sa.ForeignKeyConstraint(
            ["devis_id"], ["devis.id"], name="fk_facture_devis_id_devis", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ordre_travail_id"], ["ordre_travail.id"],
            name="fk_facture_ordre_travail_id_ordre_travail", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cree_par"], ["utilisateur.id"],
            name="fk_facture_cree_par_utilisateur", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "numero ~ '^F-[0-9]{4}-[0-9]{3,}$'", name=op.f("ck_facture_numero_format")
        ),
        sa.CheckConstraint(
            "taux_tva_bp >= 0 AND taux_tva_bp <= 10000", name=op.f("ck_facture_taux_tva_borne")
        ),
        sa.CheckConstraint("total_ht_centimes >= 0", name=op.f("ck_facture_total_ht_positif")),
        sa.CheckConstraint("total_tva_centimes >= 0", name=op.f("ck_facture_total_tva_positif")),
        sa.CheckConstraint("total_ttc_centimes >= 0", name=op.f("ck_facture_total_ttc_positif")),
        sa.CheckConstraint(
            "total_ttc_centimes = total_ht_centimes + total_tva_centimes",
            name=op.f("ck_facture_ttc_coherent"),
        ),
    )
    op.create_index("ix_facture_ordre_travail_id", "facture", ["ordre_travail_id"])
    op.create_index("ix_facture_emise_le", "facture", ["emise_le"])

    op.create_table(
        "ligne_facture",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facture_id", sa.Integer(), nullable=False),
        sa.Column("type", type_ligne, nullable=False),
        sa.Column("reference", sa.String(40), nullable=True),
        sa.Column("designation", sa.String(200), nullable=False),
        sa.Column("quantite", sa.Numeric(10, 2), nullable=False),
        sa.Column("prix_unitaire_ht_centimes", sa.BigInteger(), nullable=False),
        sa.Column("total_ht_centimes", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ligne_facture"),
        sa.ForeignKeyConstraint(
            ["facture_id"], ["facture.id"],
            name="fk_ligne_facture_facture_id_facture", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantite > 0", name=op.f("ck_ligne_facture_quantite_positive")),
        sa.CheckConstraint(
            "prix_unitaire_ht_centimes >= 0", name=op.f("ck_ligne_facture_prix_positif")
        ),
        sa.CheckConstraint("total_ht_centimes >= 0", name=op.f("ck_ligne_facture_total_positif")),
        sa.CheckConstraint(
            "char_length(btrim(designation)) > 0",
            name=op.f("ck_ligne_facture_designation_non_vide"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_ligne_facture_position_positive")),
    )
    op.create_index("ix_ligne_facture_facture_id", "ligne_facture", ["facture_id"])

    op.execute(FONCTION_IMMUABLE)
    for table in TABLES_IMMUABLES:
        op.execute(
            f"CREATE TRIGGER {table}_immuable BEFORE UPDATE OR DELETE ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION refuser_modification_facture()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_sans_truncate BEFORE TRUNCATE ON {table}"
            " FOR EACH STATEMENT EXECUTE FUNCTION refuser_modification_facture()"
        )


def downgrade() -> None:
    for table in reversed(TABLES_IMMUABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_sans_truncate ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immuable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS refuser_modification_facture()")
    op.drop_index("ix_ligne_facture_facture_id", table_name="ligne_facture")
    op.drop_table("ligne_facture")
    op.drop_index("ix_facture_emise_le", table_name="facture")
    op.drop_index("ix_facture_ordre_travail_id", table_name="facture")
    op.drop_table("facture")
    # Sans les factures, leur compteur n'a plus de sens : le garder ferait reprendre la
    # numérotation après des numéros qui n'existent plus nulle part (trou), au prochain
    # upgrade. Ce downgrade détruit des pièces comptables : à réserver au développement.
    op.execute("DELETE FROM compteur WHERE type = 'FACTURE'")
