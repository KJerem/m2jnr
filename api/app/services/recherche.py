"""Recherche du gérant (story S1.3) : clients, véhicules, ordres de travail et factures.

Une seule saisie, plusieurs lectures (`analyser_requete`, fonction pure) :
- nom : chaque mot doit se trouver dans le nom ou le prénom, sans tenir compte des accents ni
  de la casse (« helene » trouve « Hélène ») ; recherche « contient » servie par l'index
  trigrammes de la migration 0013 ;
- téléphone : une saisie faite de chiffres (espaces, points, tirets, parenthèses et « +33 »
  permis) cherche les numéros qui contiennent ces chiffres ; « +33 » et « 0033 » valent 0,
  y compris suivis du 0 national (« +33 (0)6 … ») ;
- immatriculation : lettres et chiffres mêlés, tirets facultatifs, casse ignorée
  (« gh482kl » trouve « GH-482-KL ») ; les OT du véhicule sont aussi proposés ;
- numéro d'OT (« OT-2026-003 », « 2026-003 ») et de facture (« F-2026-001 ») : par début de
  numéro.

La saisie n'entre jamais dans le SQL autrement qu'en paramètre ; dans un motif LIKE, « % »,
« _ » et « \\ » sont échappés (pris à la lettre), après la normalisation sans accents pour
le nom (unaccent change « ％ » en « % »). Vingt résultats au plus par rubrique, les
plus pertinents d'abord puis par nom ; une requête par rubrique (pas de N+1).
"""

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    String,
    and_,
    case,
    false,
    func,
    literal,
    literal_column,
    or_,
    select,
    union,
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
    if compact.startswith("+33") or chiffres.startswith("0033"):
        national = chiffres[2:] if compact.startswith("+33") else chiffres[4:]
        # « +33 (0)6 … » et « +33 06 … » : le 0 national écrit après l'indicatif ne compte
        # qu'une fois.
        chiffres = "0" + national.removeprefix("0")
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


def echapper_like_sql(valeur: ColumnElement[str]) -> ColumnElement[str]:
    """`echapper_like` côté base, à appliquer APRÈS `etabli_normaliser` : unaccent ramène
    « ％ », « ﹪ », « ＿ » et « ＼ » à « % », « _ » et « \\ », qui seraient sinon des jokers."""
    sans_barre = func.replace(valeur, "\\", "\\\\")
    return func.replace(func.replace(sans_barre, "%", "\\%"), "_", "\\_")


def _contient(colonne: ColumnElement[Any], valeur: ColumnElement[Any]) -> ColumnElement[bool]:
    return colonne.like(func.concat("%", valeur, "%"), escape="\\")


def chaque_mot_dans(texte: ColumnElement[str], mots: tuple[str, ...]) -> ColumnElement[bool]:
    """Chaque mot de la saisie se trouve dans `texte`, sans tenir compte des accents ni de la
    casse (les deux côtés passent par etabli_normaliser), jokers LIKE pris à la lettre
    (échappés après la normalisation). Sert aux recherches des listes (stories S8.2, S1.5)."""
    normalise = func.etabli_normaliser(texte)
    return and_(
        *(_contient(normalise, echapper_like_sql(func.etabli_normaliser(mot))) for mot in mots)
    )


def recherche_de_liste(q: str | None) -> str | None:
    """Paramètre `q` facultatif d'une liste (stories S8.2, S1.5) : None si absent ou vide (pas
    de filtre), sinon la saisie contrôlée par `lire_requete` (422 « q » de 2 à 100 caractères,
    sans caractère de contrôle)."""
    if q is None or not q.strip():
        return None
    return lire_requete(q)


def mots_de(q: str | None) -> tuple[str, ...] | None:
    """Mots d'un paramètre `q` facultatif de liste (voir `recherche_de_liste`)."""
    texte = recherche_de_liste(q)
    return tuple(texte.split()) if texte else None


def _nom_contient_chaque_mot(mots: tuple[str, ...]) -> ColumnElement[bool]:
    return and_(
        *(_contient(NOM_NORMALISE, echapper_like_sql(func.etabli_normaliser(mot))) for mot in mots)
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


def _condition_clients(c: Criteres) -> ColumnElement[bool]:
    """Clients trouvés par le nom, le téléphone ou la plaque d'un de leurs véhicules.

    Un OR entre ces conditions et un IN sur les véhicules empêchait PostgreSQL d'utiliser
    les index trigrammes (parcours de toute la table) : les identifiants viennent d'une
    UNION de branches servies chacune par son index ; la saisie qui n'est ni un téléphone
    ni une plaque garde la seule condition du nom, sans sous-requête."""
    par_nom = _nom_contient_chaque_mot(c.mots)
    if not c.telephone and not c.plaque:
        return par_nom
    branches: list[Select[int]] = [select(Client.id).where(par_nom)]
    if c.telephone:
        branches.append(
            select(Client.id).where(Client.telephone.contains(c.telephone, autoescape=True))
        )
    if c.plaque:
        branches.append(select(Vehicule.client_id).where(_plaque_contient(c)))
    return Client.id.in_(union(*branches))


def requete_clients(c: Criteres) -> Select[Client, int]:
    nb_vehicules = (
        select(func.count(Vehicule.id)).where(Vehicule.client_id == Client.id).scalar_subquery()
    )
    pertinence = func.greatest(
        func.similarity(NOM_NORMALISE, func.etabli_normaliser(c.texte)),
        case((Client.telephone == (c.telephone or ""), 1.0), else_=0.0),
    )
    return (
        select(Client, nb_vehicules)
        .where(_condition_clients(c))
        .order_by(
            pertinence.desc(),
            func.lower(Client.nom),
            func.lower(func.coalesce(Client.prenom, "")),
            Client.id,
        )
        .limit(RESULTATS_MAX)
    )


def _clients(db: Session, c: Criteres) -> list[ClientTrouve]:
    lignes = db.execute(requete_clients(c)).all()
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


# --- Recherche dans les listes (story S1.5) ----------------------------------------------------
#
# Chaque liste filtre côté base sur un paramètre `q` facultatif (lu par `lire_requete` : 2 à
# 100 caractères, sans caractère de contrôle, 422 sinon), sans accents ni casse, jokers LIKE
# pris à la lettre. Le filtre est une condition WHERE de la requête paginée : le total et les
# pages restent justes.

_EMAIL_POSSIBLE = re.compile(r"\S*[@.]\S*")


def _email(texte: str) -> str | None:
    """Un seul mot avec « @ » ou « . » (« c.laurent », « @exemple ») : lecture « e-mail »."""
    return texte.lower() if _EMAIL_POSSIBLE.fullmatch(texte) else None


def _plaque_liste(texte: str) -> str | None:
    """Plaque, même partielle (« GH-482 », « 482 ») : au moins un chiffre, tirets facultatifs.
    Une saisie faite de lettres seules est lue comme un nom, pas comme une plaque."""
    compacte = re.sub(r"[\s-]", "", texte).upper()
    if not _PLAQUE.fullmatch(compacte) or not any(ch.isdigit() for ch in compacte):
        return None
    return compacte


def condition_clients_liste(texte: str) -> ColumnElement[bool]:
    """Liste des clients : nom et prénom (chaque mot), téléphone (chiffres, même partiel),
    plaque d'un de leurs véhicules et, pour une saisie qui ressemble à une adresse, e-mail.

    Comme la recherche du gérant (S1.3), une UNION de branches servies par les index
    trigrammes ; la branche e-mail, sans index, n'est ajoutée que pour un mot contenant « @ »
    ou « . », et la saisie qui n'est qu'un nom garde la seule condition du nom."""
    c = analyser_requete(texte)
    par_nom = _nom_contient_chaque_mot(c.mots)
    plaque = _plaque_liste(texte)
    email = _email(c.texte)
    if not c.telephone and not plaque and not email:
        return par_nom
    branches: list[Select[int]] = [select(Client.id).where(par_nom)]
    if c.telephone:
        branches.append(
            select(Client.id).where(Client.telephone.contains(c.telephone, autoescape=True))
        )
    if plaque:
        branches.append(
            select(Vehicule.client_id).where(
                _contient(PLAQUE_COMPACTE, literal(echapper_like(plaque)))
            )
        )
    if email:
        branches.append(
            select(Client.id).where(func.lower(Client.email).contains(email, autoescape=True))
        )
    return Client.id.in_(union(*branches))


def condition_vehicules_liste(texte: str) -> ColumnElement[bool]:
    """Liste des véhicules (gérant et mécanicien) : plaque avec ou sans tirets, marque,
    modèle et VIN (chaque mot), nom du propriétaire (chaque mot). Jamais le téléphone ni
    l'e-mail du propriétaire : le mécanicien ne les voit pas.

    UNION de branches : plaque (index trigrammes de la plaque), propriétaire (index du nom
    du client), description du véhicule (marque, modèle, VIN)."""
    c = analyser_requete(texte)
    description = func.concat_ws(" ", Vehicule.marque, Vehicule.modele, Vehicule.vin)
    # Propriétaires trouvés d'abord, par l'index de leur nom (CTE matérialisée : sans elle,
    # PostgreSQL peut parcourir les véhicules et relire chaque client par sa clé, en filtrant
    # le nom ligne à ligne).
    proprietaires = (
        select(Client.id)
        .where(_nom_contient_chaque_mot(c.mots))
        .cte("proprietaires_cherches")
        .prefix_with("MATERIALIZED")
    )
    branches: list[Select[int]] = [
        select(Vehicule.id).where(Vehicule.client_id.in_(select(proprietaires.c.id))),
        select(Vehicule.id).where(chaque_mot_dans(description, c.mots)),
    ]
    plaque = _plaque_liste(texte)
    if plaque:
        branches.append(
            select(Vehicule.id).where(_contient(PLAQUE_COMPACTE, literal(echapper_like(plaque))))
        )
    return Vehicule.id.in_(union(*branches))
