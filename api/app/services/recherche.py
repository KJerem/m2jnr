"""Recherche du gérant (story S1.3) : clients, véhicules, ordres de travail et factures.

Une seule saisie, plusieurs lectures (`analyser_requete`, fonction pure) :
- nom : chaque mot doit se trouver dans le nom ou le prénom, sans tenir compte des accents ni
  de la casse (« helene » trouve « Hélène ») ; recherche « contient » servie par l'index
  trigrammes de la migration 0013 ;
- téléphone : une saisie faite de chiffres (espaces, points, tirets, parenthèses et « +33 »
  permis) cherche les numéros qui contiennent ces chiffres ; « +33 » et « 0033 » valent 0 ;
- immatriculation : lettres et chiffres mêlés, tirets facultatifs, casse ignorée
  (« gh482kl » trouve « GH-482-KL ») ; les OT du véhicule sont aussi proposés ;
- numéro d'OT (« OT-2026-003 », « 2026-003 ») et de facture (« F-2026-001 ») : par début de
  numéro.

La saisie n'entre jamais dans le SQL autrement qu'en paramètre ; dans un motif LIKE, « % »,
« _ » et « \\ » sont échappés (pris à la lettre). Vingt résultats au plus par rubrique, les
plus pertinents d'abord puis par nom ; une requête par rubrique (pas de N+1).
"""

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    ColumnElement,
    String,
    and_,
    case,
    false,
    func,
    literal,
    literal_column,
    or_,
    select,
)
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy.sql.elements import ColumnClause

from app.errors import invalid
from app.models.client import Client
from app.models.facture import Facture
from app.models.ordre_travail import OrdreTravail, StatutOT
from app.models.vehicule import Vehicule
from app.schemas.commun import MESSAGE_CARACTERE_INTERDIT, refuser_caracteres_de_controle

LONGUEUR_MIN = 2
LONGUEUR_MAX = 100
RESULTATS_MAX = 20
MESSAGE_TROP_COURT = "Saisissez au moins 2 caractères."
MESSAGE_TROP_LONG = "100 caractères au plus."

_TELEPHONE = re.compile(r"[0-9\s.()/+-]+")
_PLAQUE = re.compile(r"[A-Z0-9]{2,9}")
_ORDRE_AVEC_PREFIXE = re.compile(r"OT[\s-]?([0-9]{4})(?:[\s-]?([0-9]{0,6}))?", re.IGNORECASE)
_FACTURE = re.compile(r"F[\s-]?([0-9]{4})(?:[\s-]?([0-9]{0,6}))?", re.IGNORECASE)
_NUMERO_SANS_PREFIXE = re.compile(r"([0-9]{4})[\s-]([0-9]{1,6})")

# Même expression que l'index ix_client_nom_prenom_trgm (migration 0013) : constantes
# écrites en clair (et non en paramètres) pour que PostgreSQL reconnaisse l'index.
NOM_NORMALISE: ColumnClause[str] = literal_column(
    "etabli_normaliser(client.nom || ' ' || coalesce(client.prenom, ''))", String()
)
PLAQUE_COMPACTE: ColumnClause[str] = literal_column(
    "replace(vehicule.immatriculation, '-', '')", String()
)


@dataclass(frozen=True)
class Criteres:
    """Lectures possibles d'une saisie ; None quand une lecture ne s'applique pas."""

    texte: str
    mots: tuple[str, ...]
    telephone: str | None
    plaque: str | None
    ordre: str | None
    facture: str | None


def lire_requete(q: str | None) -> str:
    """Saisie nettoyée (espaces de bord retirés), 2 à 100 caractères, sans caractère de
    contrôle ; 422 sur le champ « q » sinon."""
    texte = (q or "").strip()
    if len(texte) < LONGUEUR_MIN:
        raise invalid("q", MESSAGE_TROP_COURT)
    if len(texte) > LONGUEUR_MAX:
        raise invalid("q", MESSAGE_TROP_LONG)
    try:
        refuser_caracteres_de_controle(texte)
    except ValueError as exc:
        raise invalid("q", MESSAGE_CARACTERE_INTERDIT) from exc
    return texte


def _telephone(texte: str) -> str | None:
    if not _TELEPHONE.fullmatch(texte):
        return None
    compact = re.sub(r"[\s.()/-]", "", texte)
    if "+" in compact[1:] or (compact.startswith("+") and not compact.startswith("+33")):
        return None
    chiffres = re.sub(r"[^0-9]", "", compact)
    if compact.startswith("+33"):
        chiffres = "0" + chiffres[2:]
    elif chiffres.startswith("0033"):
        chiffres = "0" + chiffres[4:]
    return chiffres if len(chiffres) >= LONGUEUR_MIN else None


def _plaque(texte: str) -> str | None:
    compacte = re.sub(r"[\s-]", "", texte).upper()
    if not _PLAQUE.fullmatch(compacte):
        return None
    lettres = any(c.isalpha() for c in compacte)
    chiffres = any(c.isdigit() for c in compacte)
    return compacte if lettres and chiffres else None


def _numero(prefixe: str, annee: str, rang: str | None) -> str:
    return f"{prefixe}-{annee}-{rang}" if rang else f"{prefixe}-{annee}-"


def analyser_requete(texte: str) -> Criteres:
    """Fonction pure : découpe la saisie en mots et reconnaît téléphone, plaque et numéros."""
    ordre = facture = None
    if m := _ORDRE_AVEC_PREFIXE.fullmatch(texte):
        ordre = _numero("OT", m.group(1), m.group(2))
    elif m := _FACTURE.fullmatch(texte):
        facture = _numero("F", m.group(1), m.group(2))
    elif m := _NUMERO_SANS_PREFIXE.fullmatch(texte):
        # « 2026-003 » : début d'un numéro d'OT ou de facture.
        ordre = _numero("OT", m.group(1), m.group(2))
        facture = _numero("F", m.group(1), m.group(2))
    return Criteres(
        texte=texte,
        mots=tuple(texte.split()),
        telephone=_telephone(texte),
        plaque=_plaque(texte),
        ordre=ordre,
        facture=facture,
    )


def echapper_like(texte: str) -> str:
    """« 50 % » reste « 50 % » à la lettre dans un motif LIKE (échappement « \\ »)."""
    return texte.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _contient(colonne: ColumnElement[Any], valeur: ColumnElement[Any]) -> ColumnElement[bool]:
    return colonne.like(func.concat("%", valeur, "%"), escape="\\")


def _nom_contient_chaque_mot(mots: tuple[str, ...]) -> ColumnElement[bool]:
    return and_(
        *(_contient(NOM_NORMALISE, func.etabli_normaliser(echapper_like(mot))) for mot in mots)
    )


def _criteres_client(c: Criteres) -> ColumnElement[bool]:
    conditions = [_nom_contient_chaque_mot(c.mots)]
    if c.telephone:
        conditions.append(Client.telephone.contains(c.telephone, autoescape=True))
    return or_(*conditions)


def _plaque_contient(c: Criteres) -> ColumnElement[bool]:
    if not c.plaque:
        return false()
    return _contient(PLAQUE_COMPACTE, literal(echapper_like(c.plaque)))


@dataclass(frozen=True)
class ClientTrouve:
    client: Client
    nb_vehicules: int


@dataclass(frozen=True)
class Resultats:
    clients: list[ClientTrouve]
    vehicules: list[Vehicule]
    ordres: list[OrdreTravail]
    factures: list[Facture]


def _clients(db: Session, c: Criteres) -> list[ClientTrouve]:
    nb_vehicules = (
        select(func.count(Vehicule.id)).where(Vehicule.client_id == Client.id).scalar_subquery()
    )
    proprietaires = select(Vehicule.client_id).where(_plaque_contient(c))
    pertinence = func.greatest(
        func.similarity(NOM_NORMALISE, func.etabli_normaliser(c.texte)),
        case((Client.telephone == (c.telephone or ""), 1.0), else_=0.0),
    )
    lignes = db.execute(
        select(Client, nb_vehicules)
        .where(or_(_criteres_client(c), Client.id.in_(proprietaires)))
        .order_by(
            pertinence.desc(),
            func.lower(Client.nom),
            func.lower(func.coalesce(Client.prenom, "")),
            Client.id,
        )
        .limit(RESULTATS_MAX)
    ).all()
    return [ClientTrouve(client, int(nombre)) for client, nombre in lignes]


def _vehicules(db: Session, c: Criteres) -> list[Vehicule]:
    plaque_exacte = literal(c.plaque or "") == PLAQUE_COMPACTE
    return list(
        db.scalars(
            select(Vehicule)
            .join(Vehicule.client)
            .where(or_(_plaque_contient(c), _criteres_client(c)))
            .options(contains_eager(Vehicule.client))
            .order_by(
                case((plaque_exacte, 0), (_plaque_contient(c), 1), else_=2),
                func.lower(Client.nom),
                Vehicule.immatriculation,
            )
            .limit(RESULTATS_MAX)
        )
    )


def _ordres(db: Session, c: Criteres) -> list[OrdreTravail]:
    conditions = [_plaque_contient(c)]
    numero_exact: ColumnElement[bool] = false()
    if c.ordre:
        conditions.append(OrdreTravail.numero.startswith(c.ordre, autoescape=True))
        numero_exact = OrdreTravail.numero == c.ordre
    return list(
        db.scalars(
            select(OrdreTravail)
            .join(OrdreTravail.vehicule)
            .where(or_(*conditions))
            .options(contains_eager(OrdreTravail.vehicule))
            .order_by(
                case((numero_exact, 0), else_=1),
                case((OrdreTravail.statut == StatutOT.LIVRE, 1), else_=0),
                OrdreTravail.ouvert_le.desc(),
                OrdreTravail.id.desc(),
            )
            .limit(RESULTATS_MAX)
        )
    )


def _factures(db: Session, c: Criteres) -> list[Facture]:
    if not c.facture:
        return []
    return list(
        db.scalars(
            select(Facture)
            .where(Facture.numero.startswith(c.facture, autoescape=True))
            .order_by(case((Facture.numero == c.facture, 0), else_=1), Facture.numero.desc())
            .limit(RESULTATS_MAX)
        )
    )


def rechercher(db: Session, criteres: Criteres) -> Resultats:
    return Resultats(
        clients=_clients(db, criteres),
        vehicules=_vehicules(db, criteres),
        ordres=_ordres(db, criteres),
        factures=_factures(db, criteres),
    )
