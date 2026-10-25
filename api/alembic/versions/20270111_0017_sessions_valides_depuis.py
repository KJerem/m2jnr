"""Sessions coupées à la désactivation et à la réinitialisation du mot de passe (revue du
sprint 5, story S8.2).

- utilisateur.sessions_valides_depuis (timestamptz, facultatif) : une session dont le jeton a
  été émis avant cette date (comparée à la seconde) est refusée, même si le compte est de
  nouveau actif. Mise à jour à la désactivation et à la réinitialisation du mot de passe ;
- reprise : un compte déjà désactivé reçoit sa date de désactivation, pour que ses anciens
  cookies ne reprennent pas vie à sa réactivation.

Le downgrade supprime la colonne.

Revision ID: 0017
Revises: 0016
Create Date: 2027-01-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "utilisateur",
        sa.Column("sessions_valides_depuis", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE utilisateur SET sessions_valides_depuis = desactive_le"
        " WHERE desactive_le IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("utilisateur", "sessions_valides_depuis")
