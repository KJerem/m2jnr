"""Paiements d'une facture (story S4.4) : encaissements partiels, jamais au-delà du TTC.

- type énuméré `mode_paiement` (carte | especes | cheque | virement). « carte » désigne le
  terminal de paiement du garage : aucune donnée de carte n'est saisie ni enregistrée ;
- table `paiement` : facture (FK RESTRICT), montant en centimes (> 0), mode, date de
  réception (timestamptz), référence facultative (n° de chèque, de virement), auteur et
  date d'enregistrement ;
- trigger `paiement_plafond` (BEFORE INSERT) : verrouille la facture (SELECT … FOR UPDATE,
  qui ne déclenche pas le trigger d'UPDATE de la facture), puis refuse le paiement si le
  cumul dépasse le TTC (RAISE EXCEPTION 'trop perçu', SQLSTATE ET002). Deux encaissements
  simultanés s'attendent sur ce verrou : le second voit le premier et ne peut pas dépasser ;
- triggers `paiement_immuable` / `paiement_sans_truncate` : un paiement ne se modifie ni ne
  se supprime (SQLSTATE ET003). Corriger un paiement saisi par erreur (avoir, annulation
  tracée) est hors du périmètre du MVP.

Revision ID: 0014
Revises: 0013
Create Date: 2026-12-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

mode_paiement = postgresql.ENUM(
    "carte", "especes", "cheque", "virement", name="mode_paiement", create_type=False
)

FONCTION_PLAFOND = """
CREATE FUNCTION verifier_plafond_paiement() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    total bigint;
    deja bigint;
BEGIN
    -- Verrou de la facture : les encaissements d'une même facture passent un par un.
    SELECT total_ttc_centimes INTO total FROM facture WHERE id = NEW.facture_id FOR UPDATE;
    SELECT coalesce(sum(montant_centimes), 0) INTO deja
        FROM paiement WHERE facture_id = NEW.facture_id;
    IF total IS NOT NULL AND deja + NEW.montant_centimes > total THEN
        RAISE EXCEPTION 'trop perçu'
            USING ERRCODE = 'ET002',
                  DETAIL = format(
                      'Facture %s : %s centimes déjà payés, %s de plus dépasseraient %s.',
                      NEW.facture_id, deja, NEW.montant_centimes, total);
    END IF;
    RETURN NEW;
END;
$$
"""

FONCTION_IMMUABLE = """
CREATE FUNCTION refuser_modification_paiement() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'paiement immuable'
        USING ERRCODE = 'ET003',
              DETAIL = format('%s refusé sur paiement : un paiement enregistré ne change plus.',
                              TG_OP);
END;
$$
"""


def upgrade() -> None:
    mode_paiement.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "paiement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("facture_id", sa.Integer(), nullable=False),
        sa.Column("montant_centimes", sa.BigInteger(), nullable=False),
        sa.Column("mode", mode_paiement, nullable=False),
        sa.Column("recu_le", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference", sa.String(60), nullable=True),
        sa.Column("cree_par", sa.Integer(), nullable=False),
        sa.Column(
            "cree_le", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["facture_id"],
            ["facture.id"],
            name=op.f("fk_paiement_facture_id_facture"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cree_par"],
            ["utilisateur.id"],
            name=op.f("fk_paiement_cree_par_utilisateur"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paiement")),
        sa.CheckConstraint("montant_centimes > 0", name=op.f("ck_paiement_montant_positif")),
        sa.CheckConstraint(
            "reference IS NULL OR char_length(btrim(reference)) > 0",
            name=op.f("ck_paiement_reference_non_vide"),
        ),
    )
    op.create_index("ix_paiement_facture_id", "paiement", ["facture_id"])

    op.execute(FONCTION_PLAFOND)
    op.execute(FONCTION_IMMUABLE)
    op.execute(
        "CREATE TRIGGER paiement_plafond BEFORE INSERT ON paiement"
        " FOR EACH ROW EXECUTE FUNCTION verifier_plafond_paiement()"
    )
    op.execute(
        "CREATE TRIGGER paiement_immuable BEFORE UPDATE OR DELETE ON paiement"
        " FOR EACH ROW EXECUTE FUNCTION refuser_modification_paiement()"
    )
    op.execute(
        "CREATE TRIGGER paiement_sans_truncate BEFORE TRUNCATE ON paiement"
        " FOR EACH STATEMENT EXECUTE FUNCTION refuser_modification_paiement()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS paiement_sans_truncate ON paiement")
    op.execute("DROP TRIGGER IF EXISTS paiement_immuable ON paiement")
    op.execute("DROP TRIGGER IF EXISTS paiement_plafond ON paiement")
    op.execute("DROP FUNCTION IF EXISTS refuser_modification_paiement()")
    op.execute("DROP FUNCTION IF EXISTS verifier_plafond_paiement()")
    op.drop_index("ix_paiement_facture_id", table_name="paiement")
    op.drop_table("paiement")
    mode_paiement.drop(op.get_bind(), checkfirst=True)
