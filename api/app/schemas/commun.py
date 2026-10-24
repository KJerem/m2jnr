"""Types partagés par les schémas : textes nettoyés, e-mail facultatif, pagination."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, StringConstraints

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


class Page[T](BaseModel):
    """Page de résultats : `elements` de la page demandée et `total` sur toutes les pages."""

    elements: list[T]
    total: int
    page: int
    taille: int
