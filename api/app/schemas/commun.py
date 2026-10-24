"""Types partagés par les schémas : textes nettoyés, e-mail facultatif, dates, pagination."""

import re
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, StringConstraints

from app.clock import instant_local, verifier_annee
from app.config import get_settings
from app.db import ID_MAX
from app.services.courriel import normaliser_courriel

MESSAGE_CARACTERE_INTERDIT = "Caractère non autorisé."
# Caractères de contrôle (C0, DEL, C1) sauf tabulation et retours à la ligne. PostgreSQL
# refuse NUL dans un champ texte (erreur 500 avant la revue du sprint 3) ; les autres
# n'ont rien à faire dans une fiche, un devis ou une facture.
_CARACTERES_DE_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def refuser_caracteres_de_controle(valeur: str) -> str:
    if _CARACTERES_DE_CONTROLE.search(valeur):
        raise ValueError(MESSAGE_CARACTERE_INTERDIT)
    return valeur


# À ajouter à tout texte libre saisi (après StringConstraints) : 422 sur le champ.
SansControle = AfterValidator(refuser_caracteres_de_controle)


def vide_vers_none(valeur: object) -> object:
    """Un champ texte facultatif laissé vide (ou fait d'espaces) vaut « non renseigné »."""
    if isinstance(valeur, str) and not valeur.strip():
        return None
    return valeur


TexteObligatoire100 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100), SansControle
]
TexteFacultatif100 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=100), SansControle] | None,
    BeforeValidator(vide_vers_none),
]
EmailFacultatif = Annotated[
    Annotated[str, StringConstraints(max_length=254), AfterValidator(normaliser_courriel)] | None,
    BeforeValidator(vide_vers_none),
]


def _instant_garage(valeur: datetime) -> datetime:
    # Contrôle AVANT le passage en UTC : « 0001-01-01T00:30 » à Paris déborderait déjà.
    verifier_annee(valeur)
    return instant_local(valeur, get_settings().timezone)


def _jour_borne(valeur: date) -> date:
    verifier_annee(valeur)
    return valeur


# Date et heure : avec fuseau (ISO 8601 « 2026-11-16T17:30:00+01:00 ») ou sans, lue alors à
# l'heure du garage (« 2026-11-16T17:30 », valeur d'un champ datetime-local). Rendue en UTC.
Instant = Annotated[datetime, AfterValidator(_instant_garage)]
InstantFacultatif = Annotated[Instant | None, BeforeValidator(vide_vers_none)]

# Jour « AAAA-MM-JJ » d'un paramètre de recherche (du, au, jour), entre 2000 et 2100.
Jour = Annotated[date, AfterValidator(_jour_borne)]

# Identifiant envoyé par le client : entier JSON strict (ni « 3 », ni true), dans les limites
# d'une clé INTEGER (au-delà, la base lèverait une erreur de type au lieu de ne rien trouver).
Identifiant = Annotated[int, Field(strict=True, ge=1, le=ID_MAX)]


# Borne haute du numéro de page : au-delà, le décalage SQL (page - 1) × taille déborde.
PAGE_MAX = 100_000


class Page[T](BaseModel):
    """Page de résultats : `elements` de la page demandée et `total` sur toutes les pages."""

    elements: list[T]
    total: int
    page: int
    taille: int


class FactureLien(BaseModel):
    """Facture émise à partir d'un devis (story S4.3) : lien vers sa page et son PDF."""

    id: int
    numero: str
