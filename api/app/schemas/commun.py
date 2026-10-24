"""Types partagés par les schémas : textes nettoyés, e-mail facultatif, dates, pagination."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, StringConstraints

from app.clock import instant_local
from app.config import get_settings
from app.db import ID_MAX
from app.services.courriel import normaliser_courriel


def vide_vers_none(valeur: object) -> object:
    """Un champ texte facultatif laissé vide (ou fait d'espaces) vaut « non renseigné »."""
    if isinstance(valeur, str) and not valeur.strip():
        return None
    return valeur


TexteObligatoire100 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
TexteFacultatif100 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None,
    BeforeValidator(vide_vers_none),
]
EmailFacultatif = Annotated[
    Annotated[str, StringConstraints(max_length=254), AfterValidator(normaliser_courriel)] | None,
    BeforeValidator(vide_vers_none),
]


def _instant_garage(valeur: datetime) -> datetime:
    return instant_local(valeur, get_settings().timezone)


# Date et heure : avec fuseau (ISO 8601 « 2026-11-16T17:30:00+01:00 ») ou sans, lue alors à
# l'heure du garage (« 2026-11-16T17:30 », valeur d'un champ datetime-local). Rendue en UTC.
Instant = Annotated[datetime, AfterValidator(_instant_garage)]
InstantFacultatif = Annotated[Instant | None, BeforeValidator(vide_vers_none)]

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
