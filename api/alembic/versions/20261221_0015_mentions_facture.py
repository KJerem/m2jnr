"""Mentions obligatoires de la facture (art. 242 nonies A du CGI, revue du sprint 3).

- client.adresse (200 caractères), client.code_postal (5 chiffres, contrainte
  `code_postal_format`), client.ville (100 caractères) : facultatifs (minimisation des
  données), saisis par le gérant ;
- facture.date_prestation (date, facultative) : jour de Paris de la fin de la prestation,
  figé à l'émission. Les factures déjà émises gardent NULL : ADD COLUMN ne déclenche pas les
  triggers de ligne, et aucune facture n'est mise à jour (elles restent telles qu'émises) ;
  leur PDF ne change pas.

Revision ID: 0015
Revises: 0014
Create Date: 2026-12-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("client", sa.Column("adresse", sa.String(200), nullable=True))
    op.add_column("client", sa.Column("code_postal", sa.String(5), nullable=True))
    op.add_column("client", sa.Column("ville", sa.String(100), nullable=True))
    op.create_check_constraint(
        op.f("ck_client_code_postal_format"),
        "client",
        "code_postal IS NULL OR code_postal ~ '^[0-9]{5}$'",
    )
    op.add_column("facture", sa.Column("date_prestation", sa.Date(), nullable=True))


def downgrade() -> None:
    # DROP COLUMN ne déclenche pas non plus les triggers de ligne de la facture.
    op.drop_column("facture", "date_prestation")
    op.drop_constraint("ck_client_code_postal_format", "client", type_="check")
    op.drop_column("client", "ville")
    op.drop_column("client", "code_postal")
    op.drop_column("client", "adresse")
