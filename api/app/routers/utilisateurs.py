"""Comptes des employés (story S8.2) : réservés au gérant (403 pour le mécanicien sur toutes
les routes). Le hash du mot de passe n'est jamais renvoyé."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.clock import get_now
from app.db import DbSession
from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.schemas.commun import PAGE_MAX, Page
from app.schemas.utilisateur import (
    MotDePasseEntree,
    UtilisateurEntree,
    UtilisateurModification,
    UtilisateurSortie,
    sortie_utilisateur,
)
from app.security.dependances import require_role
from app.services import comptes as service
from app.services.recherche import mots_de

gerant_seul = require_role(Role.GERANT)

router = APIRouter(prefix="/utilisateurs", tags=["employés"], dependencies=[Depends(gerant_seul)])


@router.get("")
def lister(
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    q: str | None = Query(None, description="Prénom, nom ou e-mail (2 à 100 caractères)."),
    role: Role | None = Query(None),
    statut: StatutCompte | None = Query(None),
    page: int = Query(1, ge=1, le=PAGE_MAX),
    taille: int = Query(20, ge=1, le=100),
) -> Page[UtilisateurSortie]:
    resultat = service.lister_utilisateurs(
        db, page, taille, mots=mots_de(q), role=role, statut=statut
    )
    return Page[UtilisateurSortie](
        elements=[sortie_utilisateur(u, maintenant) for u in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def creer(
    entree: UtilisateurEntree,
    db: DbSession,
    acteur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
) -> UtilisateurSortie:
    return sortie_utilisateur(service.creer_compte(db, entree, acteur, maintenant), maintenant)


@router.get("/{utilisateur_id}")
def consulter(
    utilisateur_id: int, db: DbSession, maintenant: datetime = Depends(get_now)
) -> UtilisateurSortie:
    return sortie_utilisateur(service.obtenir_utilisateur(db, utilisateur_id), maintenant)


@router.put("/{utilisateur_id}")
def modifier(
    utilisateur_id: int,
    entree: UtilisateurModification,
    db: DbSession,
    acteur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
) -> UtilisateurSortie:
    utilisateur = service.modifier_compte(db, utilisateur_id, entree, acteur)
    return sortie_utilisateur(utilisateur, maintenant)


@router.post("/{utilisateur_id}/mot-de-passe")
def reinitialiser_mot_de_passe(
    utilisateur_id: int,
    entree: MotDePasseEntree,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
) -> UtilisateurSortie:
    utilisateur = service.reinitialiser_mot_de_passe(db, utilisateur_id, entree.mot_de_passe)
    return sortie_utilisateur(utilisateur, maintenant)


@router.post("/{utilisateur_id}/debloquer")
def debloquer(
    utilisateur_id: int, db: DbSession, maintenant: datetime = Depends(get_now)
) -> UtilisateurSortie:
    return sortie_utilisateur(service.debloquer(db, utilisateur_id), maintenant)


@router.post("/{utilisateur_id}/desactiver")
def desactiver(
    utilisateur_id: int,
    db: DbSession,
    acteur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
) -> UtilisateurSortie:
    utilisateur = service.desactiver(db, utilisateur_id, acteur, maintenant)
    return sortie_utilisateur(utilisateur, maintenant)


@router.post("/{utilisateur_id}/reactiver")
def reactiver(
    utilisateur_id: int, db: DbSession, maintenant: datetime = Depends(get_now)
) -> UtilisateurSortie:
    return sortie_utilisateur(service.reactiver(db, utilisateur_id), maintenant)
