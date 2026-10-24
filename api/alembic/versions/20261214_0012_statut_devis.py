"""Statut du devis (story S4.2) : brouillon → envoyé → accepté ou refusé.

- type énuméré `statut_devis` (brouillon | envoye | accepte | refuse) ;
- devis.statut NOT NULL, « brouillon » par défaut ; devis.envoye_le, devis.decide_le
  (timestamptz) et devis.decide_par (auteur de la décision, FK utilisateur) facultatifs ;
- contrainte `statut_coherent` : un brouillon n'a ni envoi ni décision, un devis envoyé a
  une date d'envoi et pas de décision, un devis accepté ou refusé a les deux dates ;
- reprise des données : un devis déjà facturé (sprint 3) est « accepté », envoyé et décidé à
  la date d'émission de sa facture, par l'auteur de la facture ; les autres restent
  « brouillon » (valeur par défaut). Les factures ne sont pas touchées ;
- un OT peut désormais porter plusieurs devis (un devis refusé est remplacé par un nouveau),
  mais au plus UN devis non refusé : index unique partiel
  `uq_devis_ordre_non_refuse` (ordre_travail_id) WHERE statut <> 'refuse'. Jusqu'ici, l'API
  refusait tout second devis sur un OT : aucune donnée existante ne le viole.

Revision ID: 0012
Revises: 0011
Create Date: 2026-12-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

statut_devis = postgresql.ENUM(
    "brouillon", "envoye", "accepte", "refuse", name="statut_devis", create_type=False
)

CONTRAINTE_COHERENCE = (
    "(statut = 'brouillon' AND envoye_le IS NULL AND decide_le IS NULL AND decide_par IS NULL)"
    " OR (statut = 'envoye' AND envoye_le IS NOT NULL AND decide_le IS NULL"
    " AND decide_par IS NULL)"
    " OR (statut IN ('accepte', 'refuse') AND envoye_le IS NOT NULL AND decide_le IS NOT NULL"
    " AND decide_le >= envoye_le)"
)


def upgrade() -> None:
    statut_devis.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "devis",
        sa.Column(
            "statut", statut_devis, nullable=False, server_default=sa.text("'brouillon'")
        ),
    )
    op.add_column("devis", sa.Column("envoye_le", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devis", sa.Column("decide_le", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devis", sa.Column("decide_par", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_devis_decide_par_utilisateur",
        "devis",
        "utilisateur",
        ["decide_par"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Reprise : un devis facturé a forcément été accepté (le sprint 3 facturait sans statut).
    op.execute(
        "UPDATE devis SET statut = 'accepte', envoye_le = f.emise_le, decide_le = f.emise_le,"
        " decide_par = f.cree_par FROM facture f WHERE f.devis_id = devis.id"
    )

    op.create_check_constraint(op.f("ck_devis_statut_coherent"), "devis", CONTRAINTE_COHERENCE)
    op.create_index(
        "uq_devis_ordre_non_refuse",
        "devis",
        ["ordre_travail_id"],
        unique=True,
        postgresql_where=sa.text("statut <> 'refuse'"),
    )
    op.create_index("ix_devis_statut", "devis", ["statut"])


def downgrade() -> None:
    op.drop_index("ix_devis_statut", table_name="devis")
    op.drop_index("uq_devis_ordre_non_refuse", table_name="devis")
    # op.f : nom déjà complet, sans repasser par la convention de nommage (qui doublerait
    # le préfixe en « ck_devis_ck_devis_… » sous `alembic downgrade`).
    op.drop_constraint(op.f("ck_devis_statut_coherent"), "devis", type_="check")
    op.drop_constraint("fk_devis_decide_par_utilisateur", "devis", type_="foreignkey")
    op.drop_column("devis", "decide_par")
    op.drop_column("devis", "decide_le")
    op.drop_column("devis", "envoye_le")
    op.drop_column("devis", "statut")
    statut_devis.drop(op.get_bind(), checkfirst=True)
