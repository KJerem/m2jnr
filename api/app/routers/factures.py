"""Factures : réservées au gérant (403 pour le mécanicien sur toutes les routes).

Émission à partir d'un devis (numéro « F-AAAA-nnn » sans trou), liste, consultation et PDF.
Une facture émise ne se modifie pas : aucune route PUT ni DELETE, et la base refuse UPDATE
et DELETE (trigger).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status

from app.clock import bornes_jour, get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Role, Utilisateur
from app.schemas.commun import PAGE_MAX, Jour, Page
from app.schemas.facture import FactureDetail, FactureResume, detail_facture, resume_facture
from app.security.dependances import require_role
from app.services import devis as service_devis
from app.services import factures as service
from app.services import ordres as service_ordres
from app.services.pdf_facture import generer_pdf

gerant_seul = require_role(Role.GERANT)

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
    return detail_facture(service.obtenir_facture(db, facture.id))


@router.get("/factures")
def lister(
    db: DbSession,
    settings: Settings = Depends(get_settings),
    du: Jour | None = Query(None, description="Émises à partir de ce jour (Paris)"),
    au: Jour | None = Query(None, description="Émises jusqu'à ce jour inclus (Paris)"),
    page: int = Query(1, ge=1, le=PAGE_MAX),
    taille: int = Query(50, ge=1, le=200),
) -> Page[FactureResume]:
    service_ordres.jour_valide(du, au)
    depuis = bornes_jour(du, settings.timezone)[0] if du else None
    avant = bornes_jour(au, settings.timezone)[1] if au else None
    resultat = service.lister_factures(db, depuis, avant, page, taille)
    return Page[FactureResume](
        elements=[resume_facture(f) for f in resultat.elements],
        total=resultat.total,
        page=page,
        taille=taille,
    )


@router.get("/factures/{facture_id}")
def consulter(facture_id: int, db: DbSession) -> FactureDetail:
    return detail_facture(service.obtenir_facture(db, facture_id))


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
