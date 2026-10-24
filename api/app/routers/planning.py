"""Ponts et planning du jour de l'atelier (lecture seule, gérant et mécanicien)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.clock import date_locale, get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role, Utilisateur
from app.schemas.commun import Jour
from app.schemas.ordre import PontSortie, resume_ordre
from app.schemas.rendez_vous import (
    ElementPlanning,
    PlanningSortie,
    PontPlanning,
    sortie_rendez_vous,
)
from app.security.dependances import require_role
from app.services import rendez_vous as service

router = APIRouter(tags=["planning"])

tous_les_roles = require_role(Role.GERANT, Role.MECANICIEN)


@router.get("/ponts", dependencies=[Depends(tous_les_roles)])
def lister_ponts(db: DbSession) -> list[PontSortie]:
    return [PontSortie.model_validate(p) for p in service.lister_ponts(db)]


@router.get("/planning")
def planning(
    db: DbSession,
    utilisateur: Utilisateur = Depends(tous_les_roles),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
    jour: Jour | None = Query(
        None, description="Jour de Paris (AAAA-MM-JJ) ; aujourd'hui par défaut"
    ),
) -> PlanningSortie:
    donnees = service.planning_du_jour(
        db, jour or date_locale(maintenant, settings.timezone), settings.timezone
    )
    contact = utilisateur.role == Role.GERANT
    return PlanningSortie(
        jour=donnees.jour,
        ponts=[
            PontPlanning(
                id=p.pont.id,
                nom=p.pont.nom,
                charge_minutes=p.charge_minutes,
                elements=[
                    ElementPlanning(
                        type="ordre" if r.ordre else "rendez_vous",
                        heure=r.debut,
                        rendez_vous=sortie_rendez_vous(r),
                        ordre=resume_ordre(r.ordre, maintenant, voir_contact=contact)
                        if r.ordre
                        else None,
                    )
                    for r in p.rendez_vous
                ],
            )
            for p in donnees.ponts
        ],
        a_planifier=[
            resume_ordre(o, maintenant, voir_contact=contact) for o in donnees.a_planifier
        ],
    )
