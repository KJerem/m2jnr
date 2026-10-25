"""Devis : réservés au gérant (403 pour le mécanicien sur toutes les routes).

Statut (story S4.2) : POST /devis/{id}/statut fait passer le devis de brouillon à envoyé,
puis à accepté ou refusé ; seul un brouillon se modifie (PUT), seul un devis accepté se
facture, et un nouveau devis n'est possible sur un OT que si tous ses devis sont refusés.

Le mécanicien ne reçoit jamais de montant : aucune route de ce routeur ne lui répond, et la
fiche de l'OT qu'il lit ne contient aucun prix.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.clock import get_now
from app.db import DbSession
from app.errors import not_found
from app.models.utilisateur import Role, Utilisateur
from app.schemas.commun import PAGE_MAX, Page
from app.schemas.devis import (
    ChangementStatutDevisEntree,
    DevisDetail,
    DevisEntree,
    DevisResume,
    detail_devis,
    resume_devis,
)
from app.security.dependances import require_role
from app.services import devis as service
from app.services import factures as service_factures
from app.services import ordres as service_ordres
from app.services import statut_devis
from app.services.recherche import mots_de

gerant_seul = require_role(Role.GERANT)

router = APIRouter(tags=["devis"], dependencies=[Depends(gerant_seul)])


@router.post("/ordres/{ordre_id}/devis", status_code=status.HTTP_201_CREATED)
def creer(
    ordre_id: int,
    entree: DevisEntree,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
) -> DevisDetail:
    # Verrou de l'OT : deux créations simultanées ne donnent pas deux devis.
    ordre = service_ordres.obtenir_ordre(db, ordre_id, verrouiller=True)
    devis = service.creer_devis(db, ordre, entree.lignes, utilisateur, maintenant)
    return detail_devis(service.obtenir_devis(db, devis.id))


@router.get("/ordres/{ordre_id}/devis")
def devis_de_l_ordre(ordre_id: int, db: DbSession) -> DevisDetail:
    """Devis non refusé de l'OT, à défaut le dernier refusé (404 si l'OT n'en a aucun)."""
    ordre = service_ordres.obtenir_ordre(db, ordre_id)
    devis = service.devis_courant(db, ordre.id)
    if devis is None:
        raise not_found(service.MESSAGE_AUCUN_DEVIS)
    return detail_devis(devis)


@router.get("/devis")
def lister(
    db: DbSession,
    q: str | None = Query(
        None,
        description="Recherche (2 à 100 caractères) : numéro d'OT, plaque ou client.",
    ),
    page: int = Query(1, ge=1, le=PAGE_MAX),
    taille: int = Query(50, ge=1, le=200),
) -> Page[DevisResume]:
    resultat = service.lister_devis(db, page, taille, mots_de(q))
    return Page[DevisResume](
        elements=[resume_devis(d) for d in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.get("/devis/{devis_id}")
def consulter(devis_id: int, db: DbSession) -> DevisDetail:
    return detail_devis(service.obtenir_devis(db, devis_id))


@router.put("/devis/{devis_id}")
def modifier(
    devis_id: int,
    entree: DevisEntree,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
) -> DevisDetail:
    # Verrou du devis : deux enregistrements simultanés s'appliquent l'un après l'autre, et
    # une émission de facture en cours passe avant (ou après) la modification, jamais pendant.
    devis = service.obtenir_devis(db, devis_id, verrouiller=True)
    # Un devis facturé est figé (la facture en est la copie) : 409 « devis_facture » ;
    # envoyé, accepté ou refusé, il ne se modifie plus : 409 « devis_verrouille ».
    service_factures.verifier_devis_modifiable(db, devis)
    statut_devis.verifier_brouillon(devis)
    devis = service.modifier_devis(db, devis, entree.lignes, maintenant)
    return detail_devis(devis)


@router.post("/devis/{devis_id}/statut")
def changer_statut(
    devis_id: int,
    entree: ChangementStatutDevisEntree,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
) -> DevisDetail:
    # Verrou du devis : une modification, une émission de facture ou une autre décision en
    # cours passe avant (ou après), jamais en même temps.
    devis = service.obtenir_devis(db, devis_id, verrouiller=True)
    statut_devis.changer_statut_devis(devis, entree.nouveau, utilisateur, maintenant)
    db.flush()
    return detail_devis(service.obtenir_devis(db, devis.id))
