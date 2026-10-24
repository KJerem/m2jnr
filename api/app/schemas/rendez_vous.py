"""Schémas des rendez-vous, des ponts et du planning de l'atelier."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.ordre_travail import StatutOT
from app.models.rendez_vous import DUREE_MAX_MINUTES, RendezVous
from app.schemas.commun import Identifiant, Instant, SansControle
from app.schemas.ordre import ClientOrdre, OrdreResume, PontSortie, VehiculeOrdre

# Journée de travail d'un pont, pour l'indicateur de charge « 6 h 30 / 8 h ».
CAPACITE_JOUR_MINUTES = 480


class RendezVousEntree(BaseModel):
    """Prise de rendez-vous (gérant) : tous les champs sont obligatoires."""

    vehicule_id: Identifiant
    pont_id: Identifiant
    # Avec fuseau, ou sans : lu alors à l'heure de Paris (« 2026-11-19T09:00 »).
    debut: Instant
    duree_minutes: Annotated[int, Field(strict=True, ge=1, le=DUREE_MAX_MINUTES)]
    motif: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500), SansControle
    ]


class OrdreLie(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    statut: StatutOT


class RendezVousSortie(BaseModel):
    id: int
    debut: datetime
    fin: datetime
    duree_minutes: int
    motif: str
    pont: PontSortie
    vehicule: VehiculeOrdre
    # Identité seule : le planning est lu aussi par le mécanicien.
    client: ClientOrdre
    ordre: OrdreLie | None


def sortie_rendez_vous(rdv: RendezVous) -> RendezVousSortie:
    client = rdv.vehicule.client
    return RendezVousSortie(
        id=rdv.id,
        debut=rdv.debut,
        fin=rdv.fin,
        duree_minutes=rdv.duree_minutes,
        motif=rdv.motif,
        pont=PontSortie.model_validate(rdv.pont),
        vehicule=VehiculeOrdre.model_validate(rdv.vehicule),
        client=ClientOrdre(id=client.id, nom=client.nom, prenom=client.prenom),
        ordre=OrdreLie.model_validate(rdv.ordre) if rdv.ordre else None,
    )


class ElementPlanning(BaseModel):
    """Créneau d'un pont : un rendez-vous, avec la carte de son OT s'il est ouvert.

    `report` : rendez-vous d'un jour précédent dont l'OT n'est pas livré (le véhicule est
    encore sur le pont) ; `heure` vaut alors minuit du jour affiché."""

    type: Literal["rendez_vous", "ordre"]
    heure: datetime
    rendez_vous: RendezVousSortie
    ordre: OrdreResume | None = None
    report: bool = False


class PontPlanning(BaseModel):
    id: int
    nom: str
    charge_minutes: int
    capacite_minutes: int = CAPACITE_JOUR_MINUTES
    elements: list[ElementPlanning]


class PlanningSortie(BaseModel):
    jour: date
    ponts: list[PontPlanning]
    # OT non livrés sans rendez-vous : colonne « À planifier ».
    a_planifier: list[OrdreResume]
