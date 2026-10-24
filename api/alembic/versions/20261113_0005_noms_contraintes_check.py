"""Renomme les contraintes CHECK créées avec un double préfixe (ck_client_ck_client_…).

Les migrations 0002 à 0004 passaient un nom déjà préfixé, auquel la convention de nommage
de la métadonnée (« ck_%(table_name)s_%(constraint_name)s ») ajoutait un second préfixe.
Les noms en base rejoignent ici ceux du modèle. Les migrations suivantes donnent le nom
court (name="telephone_normalise") ou op.f("ck_client_telephone_normalise").

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTRAINTES: dict[str, list[str]] = {
    "utilisateur": ["tentatives_positives"],
    "client": ["nom_non_vide", "telephone_normalise"],
    "vehicule": [
        "immatriculation_siv",
        "kilometrage_positif",
        "vin_format",
        "marque_non_vide",
        "modele_non_vide",
    ],
}


def _renommer(sens_inverse: bool) -> None:
    for table, noms in CONTRAINTES.items():
        for nom in noms:
            correct = f"ck_{table}_{nom}"
            double = f"ck_{table}_{correct}"
            ancien, nouveau = (correct, double) if sens_inverse else (double, correct)
            op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{ancien}" TO "{nouveau}"')


def upgrade() -> None:
    _renommer(sens_inverse=False)


def downgrade() -> None:
    _renommer(sens_inverse=True)
