"""Comptes des employés (story S8.2) : prénom, statut du compte, validation et désactivation.

- utilisateur.prenom (100 caractères, obligatoire) : repris du nom existant, coupé au premier
  espace (« Nadia Benali » → prénom « Nadia », nom « Benali » ; « Karim B. » → « Karim »,
  « B. »). Un nom d'un seul mot devient le prénom et le nom reste vide (« Admin » → prénom
  « Admin », nom « ») : le nom affiché, prénom puis nom, reste identique à l'ancien ;
- utilisateur.statut (type `statut_compte` : actif, en_attente, desactive) remplace le booléen
  `actif` : un compte actif le reste, un compte inactif devient « desactive ». Une seule
  colonne fait foi (pas de booléen à tenir à jour en parallèle) ; le modèle garde une
  propriété `actif` en lecture (statut = actif), et seule la valeur « actif » ouvre une
  session ;
- valide_le / valide_par : validation d'une inscription par un gérant (story S8.3) ;
- desactive_le / desactive_par : dernière désactivation (gérant qui l'a faite). Les deux
  références sont mises à NULL si le compte du gérant disparaît.

Le downgrade rend le schéma précédent : nom = prénom + nom, `actif` = (statut = actif) ; un
compte en attente redevient donc un compte inactif.

Revision ID: 0016
Revises: 0015
Create Date: 2027-01-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

statut_compte = postgresql.ENUM(
    "actif", "en_attente", "desactive", name="statut_compte", create_type=False
)

# Nom sans espaces de bord, puis position du premier espace (0 s'il n'y en a pas).
_NOM = "btrim(nom)"
_ESPACE = f"position(' ' in {_NOM})"


def upgrade() -> None:
    op.add_column("utilisateur", sa.Column("prenom", sa.String(100), nullable=True))
    # Les deux expressions lisent l'ancienne valeur de `nom` (même UPDATE).
    op.execute(
        f"UPDATE utilisateur SET"
        f" prenom = CASE WHEN {_ESPACE} > 0 THEN split_part({_NOM}, ' ', 1) ELSE {_NOM} END,"
        f" nom = CASE WHEN {_ESPACE} > 0 THEN btrim(substr({_NOM}, {_ESPACE} + 1)) ELSE '' END"
    )
    op.alter_column("utilisateur", "prenom", nullable=False)

    statut_compte.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "utilisateur",
        sa.Column("statut", statut_compte, nullable=False, server_default=sa.text("'actif'")),
    )
    op.execute("UPDATE utilisateur SET statut = 'desactive' WHERE NOT actif")
    op.drop_column("utilisateur", "actif")

    for colonne in ("valide", "desactive"):
        op.add_column(
            "utilisateur", sa.Column(f"{colonne}_le", sa.DateTime(timezone=True), nullable=True)
        )
        op.add_column("utilisateur", sa.Column(f"{colonne}_par", sa.Integer(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_utilisateur_{colonne}_par_utilisateur"),
            "utilisateur",
            "utilisateur",
            [f"{colonne}_par"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for colonne in ("desactive", "valide"):
        op.drop_constraint(
            op.f(f"fk_utilisateur_{colonne}_par_utilisateur"), "utilisateur", type_="foreignkey"
        )
        op.drop_column("utilisateur", f"{colonne}_par")
        op.drop_column("utilisateur", f"{colonne}_le")

    op.add_column(
        "utilisateur",
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute("UPDATE utilisateur SET actif = (statut = 'actif')")
    op.drop_column("utilisateur", "statut")
    statut_compte.drop(op.get_bind(), checkfirst=True)

    op.execute("UPDATE utilisateur SET nom = left(btrim(prenom || ' ' || nom), 100)")
    op.drop_column("utilisateur", "prenom")
