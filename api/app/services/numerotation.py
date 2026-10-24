"""Numérotation continue et sans trou des documents : « OT-2026-001 », « F-2026-001 »…

Principe : une ligne `compteur` par type de document et par année.

1. `INSERT … ON CONFLICT DO NOTHING` crée la ligne de l'année si elle manque (deux créations
   simultanées ne peuvent pas la créer deux fois) ;
2. `SELECT … FOR UPDATE` verrouille cette ligne jusqu'à la fin de la transaction : une autre
   création attend son tour, puis lit la valeur validée ;
3. l'incrément est écrit dans la MÊME transaction que le document. Si le document n'est pas
   enregistré (erreur, annulation), l'incrément est annulé avec lui : aucun numéro perdu.

L'année est celle du jour à Paris (horloge injectée), calculée par l'appelant.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.compteur import Compteur

TYPE_ORDRE_TRAVAIL = "OT"
# Factures : compteur de type « FACTURE », numéros préfixés « F » (« F-2026-001 »).
TYPE_FACTURE = "FACTURE"
PREFIXE_FACTURE = "F"


def formater_numero(type_document: str, annee: int, rang: int) -> str:
    """« OT », 2026, 7 → « OT-2026-007 » : trois chiffres au moins, davantage après 999."""
    return f"{type_document}-{annee}-{rang:03d}"


def prochain_rang(db: Session, type_document: str, annee: int) -> int:
    """Réserve le rang suivant pour ce type et cette année (verrou jusqu'à la fin de la
    transaction en cours)."""
    db.execute(
        insert(Compteur)
        .values(type=type_document, annee=annee, dernier=0)
        .on_conflict_do_nothing(index_elements=[Compteur.type, Compteur.annee])
    )
    compteur = db.scalars(
        select(Compteur)
        .where(Compteur.type == type_document, Compteur.annee == annee)
        .with_for_update()
        # Relit la valeur en base même si la ligne est déjà dans la session.
        .execution_options(populate_existing=True)
    ).one()
    compteur.dernier += 1
    db.flush()
    return compteur.dernier


def prochain_numero(db: Session, type_document: str, annee: int, prefixe: str | None = None) -> str:
    """Numéro complet du prochain document, par exemple « OT-2026-001 » ; le préfixe vaut le
    type du compteur sauf mention contraire (type « FACTURE », préfixe « F »)."""
    rang = prochain_rang(db, type_document, annee)
    return formater_numero(prefixe or type_document, annee, rang)
