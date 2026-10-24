"""Ordres de travail : lecture pour les deux rôles, ouverture et modification par le gérant.

Le mécanicien voit tous les OT (il peut reprendre le travail d'un collègue), mais le client
ne lui est montré que par son nom : ni téléphone ni e-mail. Les deux rôles font avancer le
statut et cochent les tâches ; l'historique enregistre qui a fait quoi.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.clock import bornes_jour, date_locale, get_now
from app.config import Settings, get_settings
from app.db import ID_MAX, DbSession
from app.models.ordre_travail import StatutOT
from app.models.utilisateur import Role, Utilisateur
from app.schemas.commun import PAGE_MAX, Jour, Page
from app.schemas.ordre import (
    ChangementStatutEntree,
    OrdreDetail,
    OrdreEntree,
    OrdreModification,
    OrdreResume,
    detail_ordre,
    resume_ordre,
)
from app.security.dependances import require_role
from app.services import ordres as service
from app.services import transitions

router = APIRouter(prefix="/ordres", tags=["ordres de travail"])

gerant_seul = require_role(Role.GERANT)
tous_les_roles = require_role(Role.GERANT, Role.MECANICIEN)


def voit_le_contact(utilisateur: Utilisateur) -> bool:
    return utilisateur.role == Role.GERANT


@router.get("")
def lister(
    db: DbSession,
    utilisateur: Utilisateur = Depends(tous_les_roles),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
    statut: list[StatutOT] | None = Query(
        None, description="Répétable : ?statut=a_faire&statut=en_cours"
    ),
    mecanicien_id: int | None = Query(None, ge=1, le=ID_MAX),
    vehicule_id: int | None = Query(None, ge=1, le=ID_MAX),
    du: Jour | None = Query(None, description="Ouverts à partir de ce jour (Paris)"),
    au: Jour | None = Query(None, description="Ouverts jusqu'à ce jour inclus (Paris)"),
    atelier: bool = Query(False, description="Vue atelier : non livrés et livrés du jour"),
    page: int = Query(1, ge=1, le=PAGE_MAX),
    taille: int = Query(50, ge=1, le=200),
) -> Page[OrdreResume]:
    service.jour_valide(du, au)
    filtres = service.FiltresOrdres(
        statuts=statut or (),
        mecanicien_id=mecanicien_id,
        vehicule_id=vehicule_id,
        ouvert_depuis=bornes_jour(du, settings.timezone)[0] if du else None,
        ouvert_avant=bornes_jour(au, settings.timezone)[1] if au else None,
        livres_depuis=(
            bornes_jour(date_locale(maintenant, settings.timezone), settings.timezone)[0]
            if atelier
            else None
        ),
    )
    resultat = service.lister_ordres(db, filtres, page, taille)
    contact = voit_le_contact(utilisateur)
    return Page[OrdreResume](
        elements=[resume_ordre(o, maintenant, voir_contact=contact) for o in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def creer(
    entree: OrdreEntree,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> OrdreDetail:
    # Numérotation annuelle : l'année du jour à Paris (le 31 décembre à 23 h 30 compte encore).
    annee = date_locale(maintenant, settings.timezone).year
    ordre = service.creer_ordre(db, entree, utilisateur, maintenant, annee)
    return detail_ordre(service.obtenir_ordre(db, ordre.id), maintenant, voir_contact=True)


@router.get("/{ordre_id}")
def consulter(
    ordre_id: int,
    db: DbSession,
    utilisateur: Utilisateur = Depends(tous_les_roles),
    maintenant: datetime = Depends(get_now),
) -> OrdreDetail:
    ordre = service.obtenir_ordre(db, ordre_id)
    return detail_ordre(ordre, maintenant, voir_contact=voit_le_contact(utilisateur))


@router.put("/{ordre_id}")
def modifier(
    ordre_id: int,
    entree: OrdreModification,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
) -> OrdreDetail:
    # Verrou de l'OT, comme pour le statut et les tâches : la règle « Prêt » (pas de nouvelle
    # tâche) et « Livré » (plus rien de modifiable) se vérifie sur l'état validé le plus récent.
    ordre = service.obtenir_ordre(db, ordre_id, verrouiller=True)
    ordre = service.modifier_ordre(db, ordre, entree)
    return detail_ordre(ordre, maintenant, voir_contact=True)


@router.post("/{ordre_id}/statut")
def changer_statut(
    ordre_id: int,
    entree: ChangementStatutEntree,
    db: DbSession,
    utilisateur: Utilisateur = Depends(tous_les_roles),
    maintenant: datetime = Depends(get_now),
) -> OrdreDetail:
    ordre = service.obtenir_ordre(db, ordre_id, verrouiller=True)
    transitions.changer_statut(ordre, entree.nouveau, utilisateur, maintenant)
    db.flush()
    return detail_ordre(ordre, maintenant, voir_contact=voit_le_contact(utilisateur))


@router.post("/{ordre_id}/taches/{tache_id}/terminer")
def terminer_tache(
    ordre_id: int,
    tache_id: int,
    db: DbSession,
    utilisateur: Utilisateur = Depends(tous_les_roles),
    maintenant: datetime = Depends(get_now),
) -> OrdreDetail:
    ordre = service.obtenir_ordre(db, ordre_id, verrouiller=True)
    transitions.terminer_tache(ordre, tache_id, utilisateur, maintenant)
    db.flush()
    return detail_ordre(ordre, maintenant, voir_contact=voit_le_contact(utilisateur))


@router.post("/{ordre_id}/taches/{tache_id}/rouvrir")
def rouvrir_tache(
    ordre_id: int,
    tache_id: int,
    db: DbSession,
    utilisateur: Utilisateur = Depends(tous_les_roles),
    maintenant: datetime = Depends(get_now),
) -> OrdreDetail:
    ordre = service.obtenir_ordre(db, ordre_id, verrouiller=True)
    transitions.rouvrir_tache(ordre, tache_id)
    db.flush()
    return detail_ordre(ordre, maintenant, voir_contact=voit_le_contact(utilisateur))
