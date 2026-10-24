"""Recherche par nom, téléphone ou immatriculation (story S1.3).

- extension `unaccent` (contrib de PostgreSQL, disponible dans l'image postgres:16-alpine) ;
- fonction `etabli_normaliser(text)` : minuscules sans accents (« Hélène » → « helene »).
  `unaccent(text)` n'est que STABLE (son dictionnaire se change à chaud) : un index ne peut
  pas l'utiliser. L'enveloppe IMMUTABLE nomme explicitement le dictionnaire
  (`public.unaccent`), forme recommandée par la documentation de PostgreSQL ;
- index GIN trigrammes (`pg_trgm`, migration 0001) qui servent les recherches
  « contient » (LIKE '%…%') :
  * `ix_client_nom_prenom_trgm` sur etabli_normaliser(nom || ' ' || prénom),
  * `ix_client_telephone_trgm` sur le téléphone (déjà normalisé : 10 chiffres),
  * `ix_vehicule_immatriculation_trgm` sur la plaque sans tirets (« GH482KL »).

Les numéros d'OT et de facture ont déjà leur index unique (btree), suffisant pour une
recherche par préfixe ou numéro exact.

Revision ID: 0013
Revises: 0012
Create Date: 2026-12-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FONCTION_NORMALISER = """
CREATE FUNCTION etabli_normaliser(texte text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
AS $$ SELECT lower(public.unaccent('public.unaccent'::regdictionary, texte)) $$
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public")
    op.execute(FONCTION_NORMALISER)
    op.execute(
        "CREATE INDEX ix_client_nom_prenom_trgm ON client USING gin"
        " (etabli_normaliser(nom || ' ' || coalesce(prenom, '')) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_client_telephone_trgm ON client USING gin (telephone gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_vehicule_immatriculation_trgm ON vehicule USING gin"
        " (replace(immatriculation, '-', '') gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vehicule_immatriculation_trgm")
    op.execute("DROP INDEX IF EXISTS ix_client_telephone_trgm")
    op.execute("DROP INDEX IF EXISTS ix_client_nom_prenom_trgm")
    op.execute("DROP FUNCTION IF EXISTS etabli_normaliser(text)")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
