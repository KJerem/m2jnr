"""Rendez-vous : lecture pour les deux rôles ; prise de rendez-vous et ouverture d'OT : gérant."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.clock import bornes_jour, date_locale, get_now
from app.config import Settings, get_settings
from app.db import ID_MAX, DbSession
from app.models.utilisateur import Role, Utilisateur
from app.schemas.commun import Jour
from app.schemas.ordre import OrdreDetail, detail_ordre
from app.schemas.rendez_vous import RendezVousEntree, RendezVousSortie, sortie_rendez_vous
from app.security.dependances import require_role
from app.services import ordres as service_ordres
from app.services import rendez_vous as service

router = APIRouter(prefix="/rendez-vous", tags=["rendez-vous"])

gerant_seul = require_role(Role.GERANT)
tous_les_roles = require_role(Role.GERANT, Role.MECANICIEN)


@router.get("", dependencies=[Depends(tous_les_roles)])
def lister(
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
    du: Jour | None = Query(
        None, description="À partir de ce jour (Paris) ; aujourd'hui par défaut"
    ),
    au: Jour | None = Query(None, description="Jusqu'à ce jour inclus (Paris)"),
    pont_id: int | None = Query(None, ge=1, le=ID_MAX),
) -> list[RendezVousSortie]:
    premier_jour = du or date_locale(maintenant, settings.timezone)
    service_ordres.jour_valide(premier_jour, au)
    depuis = bornes_jour(premier_jour, settings.timezone)[0]
    avant = bornes_jour(au, settings.timezone)[1] if au else None
    return [sortie_rendez_vous(r) for r in service.lister_rendez_vous(db, depuis, avant, pont_id)]


@router.post("", status_code=status.HTTP_201_CREATED)
def creer(
    entree: RendezVousEntree,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> RendezVousSortie:
    rdv = service.creer_rendez_vous(db, entree, utilisateur, maintenant, settings.timezone)
    return sortie_rendez_vous(service.obtenir_rendez_vous(db, rdv.id))


@router.post("/{rdv_id}/ordre", status_code=status.HTTP_201_CREATED)
def ouvrir_ordre(
    rdv_id: int,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> OrdreDetail:
    rdv = service.obtenir_rendez_vous(db, rdv_id, verrouiller=True)
    annee = date_locale(maintenant, settings.timezone).year
    ordre = service.ouvrir_ordre(db, rdv, utilisateur, maintenant, annee)
    return detail_ordre(service_ordres.obtenir_ordre(db, ordre.id), maintenant, voir_contact=True)
