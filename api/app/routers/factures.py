"""Factures : réservées au gérant (403 pour le mécanicien sur toutes les routes).

Émission à partir d'un devis (numéro « F-AAAA-nnn » sans trou), liste, consultation et PDF.
Une facture émise ne se modifie pas : aucune route PUT ni DELETE, et la base refuse UPDATE
et DELETE (trigger).

Paiements (story S4.4) : POST /factures/{id}/paiements enregistre un encaissement partiel ou
total, jamais au-delà du TTC (409 `trop_percu`) ; la facture expose ses paiements, le déjà
payé, le reste à payer, son statut de paiement et son retard. Le PDF ne change pas.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Response, status

from app.clock import bornes_jour, date_locale, get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role, Utilisateur
from app.schemas.commun import PAGE_MAX, Jour, Page
from app.schemas.facture import (
    FactureDetail,
    FactureResume,
    PaiementEntree,
    detail_facture,
    resume_facture,
)
from app.security.dependances import require_role
from app.services import devis as service_devis
from app.services import factures as service
from app.services import ordres as service_ordres
from app.services import paiements as service_paiements
from app.services.paiements import StatutPaiement
from app.services.pdf_facture import generer_pdf
from app.services.recherche import mots_de

gerant_seul = require_role(Role.GERANT)


def aujourd_hui(
    maintenant: datetime = Depends(get_now), settings: Settings = Depends(get_settings)
) -> date:
    """Jour de Paris (retard de paiement : échéance dépassée)."""
    return date_locale(maintenant, settings.timezone)


router = APIRouter(tags=["factures"], dependencies=[Depends(gerant_seul)])


@router.post("/devis/{devis_id}/facture", status_code=status.HTTP_201_CREATED)
def etablir(
    devis_id: int,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> FactureDetail:
    # Verrou du devis : une modification ou une autre émission en cours passe d'abord.
    devis = service_devis.obtenir_devis(db, devis_id, verrouiller=True)
    facture = service.etablir_facture(db, devis, utilisateur, maintenant, settings)
    jour = date_locale(maintenant, settings.timezone)
    return detail_facture(service.obtenir_facture(db, facture.id), jour)


@router.get("/factures")
def lister(
    db: DbSession,
    settings: Settings = Depends(get_settings),
    jour: date = Depends(aujourd_hui),
    du: Jour | None = Query(None, description="Émises à partir de ce jour (Paris)"),
    au: Jour | None = Query(None, description="Émises jusqu'à ce jour inclus (Paris)"),
    statut_paiement: StatutPaiement | None = Query(
        None, description="impayee, partielle ou payee (story S4.4)"
    ),
    q: str | None = Query(
        None,
        description=(
            "Recherche (2 à 100 caractères) : numéro de facture ou d'OT, client ou plaque"
            " figés sur la facture."
        ),
    ),
    page: int = Query(1, ge=1, le=PAGE_MAX),
    taille: int = Query(50, ge=1, le=200),
) -> Page[FactureResume]:
    service_ordres.jour_valide(du, au)
    depuis = bornes_jour(du, settings.timezone)[0] if du else None
    avant = bornes_jour(au, settings.timezone)[1] if au else None
    resultat = service.lister_factures(db, depuis, avant, page, taille, statut_paiement, mots_de(q))
    return Page[FactureResume](
        elements=[resume_facture(f, jour) for f in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.get("/factures/{facture_id}")
def consulter(facture_id: int, db: DbSession, jour: date = Depends(aujourd_hui)) -> FactureDetail:
    return detail_facture(service.obtenir_facture(db, facture_id), jour)


@router.post("/factures/{facture_id}/paiements", status_code=status.HTTP_201_CREATED)
def encaisser(
    facture_id: int,
    entree: PaiementEntree,
    db: DbSession,
    utilisateur: Utilisateur = Depends(gerant_seul),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> FactureDetail:
    """Enregistre un paiement ; renvoie la facture avec son nouveau solde."""
    # Verrou de la facture : deux encaissements simultanés passent l'un après l'autre.
    facture = service.obtenir_facture(db, facture_id, verrouiller=True)
    service_paiements.enregistrer_paiement(
        db,
        facture,
        montant_centimes=entree.montant_centimes,
        mode=entree.mode,
        recu_le=entree.recu_le,
        reference=entree.reference,
        auteur=utilisateur,
        maintenant=maintenant,
        fuseau=settings.timezone,
    )
    db.expire(facture)
    jour = date_locale(maintenant, settings.timezone)
    return detail_facture(service.obtenir_facture(db, facture_id), jour)


@router.get(
    "/factures/{facture_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF de la facture"}},
)
def telecharger(
    facture_id: int, db: DbSession, settings: Settings = Depends(get_settings)
) -> Response:
    facture = service.obtenir_facture(db, facture_id)
    return Response(
        content=generer_pdf(facture, settings.timezone),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{facture.numero}.pdf"',
            "Cache-Control": "no-store",
        },
    )
