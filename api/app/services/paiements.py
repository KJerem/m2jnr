"""Paiements d'une facture (story S4.4) : encaissements partiels, solde, statut, retard.

Règles :
- un paiement a un montant entier en centimes, strictement positif ; son mode est carte (le
  terminal du garage : aucune donnée de carte n'est enregistrée), espèces, chèque ou
  virement ; sa référence (n° de chèque, de virement) est facultative ;
- sa date de réception vaut, par défaut, l'instant de l'enregistrement (horloge injectée) ;
  elle n'est ni dans le futur ni avant l'émission de la facture ;
- le cumul des paiements ne dépasse jamais le TTC de la facture : la base le garantit
  (trigger `paiement_plafond`, migration 0014), l'API le vérifie d'abord pour répondre
  clairement ;
- statut : « impayée » (rien reçu), « partielle » (une partie reçue), « payée » (reste nul) ;
  une facture non payée dont l'échéance est passée (jour de Paris) est « en retard » ;
- un paiement ne se modifie ni ne se supprime (trigger de la base) ; le PDF de la facture
  ne change pas avec les paiements (document émis, immuable).

Ordre des contrôles de POST /factures/{id}/paiements, facture verrouillée (SELECT … FOR
UPDATE) — le premier qui échoue répond :
  1. facture inconnue → 404 ;
  2. facture déjà payée → 409 `facture_payee` ;
  3. date de réception dans le futur ou avant l'émission → 422 sur `recu_le` ;
  4. montant supérieur au reste à payer → 409 `trop_percu` (avec `reste_centimes`).
"""

import enum
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.clock import date_locale
from app.errors import AppError, conflict, invalid
from app.models.facture import Facture
from app.models.paiement import SQLSTATE_TROP_PERCU, ModePaiement, Paiement
from app.models.utilisateur import Utilisateur
from app.services.format import formater_date, formater_euros, formater_heure

MESSAGE_FACTURE_PAYEE = "Cette facture est déjà payée."
MESSAGE_DATE_FUTURE = "La date de réception ne peut pas être dans le futur."


class StatutPaiement(enum.StrEnum):
    IMPAYEE = "impayee"
    PARTIELLE = "partielle"
    PAYEE = "payee"


@dataclass(frozen=True)
class Solde:
    deja_paye_centimes: int
    reste_centimes: int
    statut: StatutPaiement


def solde(total_ttc_centimes: int, deja_paye_centimes: int) -> Solde:
    """Fonction pure : déjà payé, reste à payer et statut d'une facture."""
    reste = max(0, total_ttc_centimes - deja_paye_centimes)
    if reste == 0:
        statut = StatutPaiement.PAYEE
    elif deja_paye_centimes > 0:
        statut = StatutPaiement.PARTIELLE
    else:
        statut = StatutPaiement.IMPAYEE
    return Solde(deja_paye_centimes, reste, statut)


def en_retard(statut: StatutPaiement, echeance: date, aujourd_hui: date) -> bool:
    """Fonction pure : non payée et échéance dépassée (le jour de l'échéance n'est pas en
    retard)."""
    return statut != StatutPaiement.PAYEE and echeance < aujourd_hui


def solde_facture(facture: Facture) -> Solde:
    return solde(facture.total_ttc_centimes, sum(p.montant_centimes for p in facture.paiements))


def message_trop_percu(reste_centimes: int) -> str:
    return f"Le paiement dépasse le reste à payer ({formater_euros(reste_centimes)})."


def trop_percu(reste_centimes: int) -> AppError:
    return conflict("trop_percu", message_trop_percu(reste_centimes), reste_centimes=reste_centimes)


def message_avant_emission(facture: Facture, fuseau: str) -> str:
    """« Le paiement ne peut pas précéder l'émission de la facture (22/12/2026 à 9 h 40). »"""
    emise = facture.emise_le
    return (
        "Le paiement ne peut pas précéder l'émission de la facture "
        f"({formater_date(date_locale(emise, fuseau))} à {formater_heure(emise, fuseau)})."
    )


def deja_paye(db: Session, facture_id: int) -> int:
    """Cumul relu en base (et non dans la session) : après le verrou de la facture, un
    paiement validé entre-temps par une autre transaction est compté."""
    total = db.scalar(
        select(func.coalesce(func.sum(Paiement.montant_centimes), 0)).where(
            Paiement.facture_id == facture_id
        )
    )
    return int(total or 0)


def enregistrer_paiement(
    db: Session,
    facture: Facture,
    *,
    montant_centimes: int,
    mode: ModePaiement,
    recu_le: datetime | None,
    reference: str | None,
    auteur: Utilisateur,
    maintenant: datetime,
    fuseau: str,
) -> Paiement:
    """Enregistre un paiement sur la facture, verrouillée par l'appelant."""
    reste = solde(facture.total_ttc_centimes, deja_paye(db, facture.id)).reste_centimes
    if reste == 0:
        raise conflict("facture_payee", MESSAGE_FACTURE_PAYEE, reste_centimes=0)
    recu = recu_le if recu_le is not None else maintenant
    if recu > maintenant:
        raise invalid("recu_le", MESSAGE_DATE_FUTURE)
    # Comparaison à la minute : le formulaire envoie « 14:47 » pour une facture émise à
    # 14 h 47 min 40 s, et le message n'affiche que la minute. Un paiement saisi dans la
    # minute de l'émission est daté de l'émission, jamais avant elle.
    if recu < facture.emise_le.replace(second=0, microsecond=0):
        raise invalid("recu_le", message_avant_emission(facture, fuseau))
    recu = max(recu, facture.emise_le)
    if montant_centimes > reste:
        raise trop_percu(reste)

    paiement = Paiement(
        facture_id=facture.id,
        montant_centimes=montant_centimes,
        mode=mode,
        recu_le=recu,
        reference=reference,
        cree_par=auteur.id,
        cree_le=maintenant,
    )
    try:
        # Point de sauvegarde : si la base refuse malgré tout le dépassement (paiement
        # enregistré hors de l'API entre-temps), la réponse reste un 409 clair.
        with db.begin_nested():
            db.add(paiement)
            db.flush()
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) != SQLSTATE_TROP_PERCU:
            raise
        raise trop_percu(
            solde(facture.total_ttc_centimes, deja_paye(db, facture.id)).reste_centimes
        ) from exc
    return paiement


# --- Filtre de la liste des factures -------------------------------------------------------


def _deja_paye_sql() -> ColumnElement[int]:
    return (
        select(func.coalesce(func.sum(Paiement.montant_centimes), 0))
        .where(Paiement.facture_id == Facture.id)
        .correlate(Facture)
        .scalar_subquery()
    )


def condition_statut(statut: StatutPaiement) -> ColumnElement[bool]:
    """Condition SQL équivalente à `solde(...).statut == statut`."""
    paye = _deja_paye_sql()
    if statut == StatutPaiement.PAYEE:
        return paye >= Facture.total_ttc_centimes
    if statut == StatutPaiement.PARTIELLE:
        return and_(paye > 0, paye < Facture.total_ttc_centimes)
    return and_(paye == 0, Facture.total_ttc_centimes > 0)
