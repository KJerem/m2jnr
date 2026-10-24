"""Lignes de facture figées dès l'émission : INSERT refusé après coup (revue du sprint 3).

La migration 0010 refuse UPDATE, DELETE et TRUNCATE sur facture et ligne_facture, mais un
INSERT dans ligne_facture restait possible sur une facture déjà émise : une ligne ajoutée en
SQL direct apparaissait dans le PDF alors que les totaux de la facture ne changeaient pas.

- trigger `facture_lignes_ouvertes` (AFTER INSERT ON facture) : note l'identifiant de la
  facture dans le paramètre de transaction `etabli.factures_en_creation` (set_config local :
  il disparaît à la fin de la transaction, ou avec le point de sauvegarde annulé) ;
- trigger `ligne_facture_ajout` (BEFORE INSERT ON ligne_facture) : refuse la ligne si sa
  facture n'a pas été créée dans la transaction en cours (RAISE EXCEPTION 'facture immuable',
  SQLSTATE ET001, comme 0010).

L'émission (facture puis ses lignes, dans la même transaction) n'est pas changée. Comme pour
désactiver un trigger, contourner la règle demande un geste explicite (SET LOCAL du
paramètre) : la protection vise les modifications accidentelles ou silencieuses.

Revision ID: 0011
Revises: 0010
Create Date: 2026-12-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FONCTION_NOTER = """
CREATE FUNCTION noter_facture_en_creation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config(
        'etabli.factures_en_creation',
        concat_ws(',', nullif(current_setting('etabli.factures_en_creation', true), ''), NEW.id),
        true
    );
    RETURN NULL;
END;
$$
"""

FONCTION_REFUSER = """
CREATE FUNCTION refuser_ligne_facture_ajoutee() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.facture_id::text = ANY (
        string_to_array(coalesce(current_setting('etabli.factures_en_creation', true), ''), ',')
    ) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'facture immuable'
        USING ERRCODE = 'ET001',
              DETAIL = format('INSERT refusé sur ligne_facture : la facture %s est déjà émise.',
                              NEW.facture_id);
END;
$$
"""


def upgrade() -> None:
    op.execute(FONCTION_NOTER)
    op.execute(FONCTION_REFUSER)
    op.execute(
        "CREATE TRIGGER facture_lignes_ouvertes AFTER INSERT ON facture"
        " FOR EACH ROW EXECUTE FUNCTION noter_facture_en_creation()"
    )
    op.execute(
        "CREATE TRIGGER ligne_facture_ajout BEFORE INSERT ON ligne_facture"
        " FOR EACH ROW EXECUTE FUNCTION refuser_ligne_facture_ajoutee()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS ligne_facture_ajout ON ligne_facture")
    op.execute("DROP TRIGGER IF EXISTS facture_lignes_ouvertes ON facture")
    op.execute("DROP FUNCTION IF EXISTS refuser_ligne_facture_ajoutee()")
    op.execute("DROP FUNCTION IF EXISTS noter_facture_en_creation()")
