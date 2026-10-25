"""Connexion, inscription, déconnexion et session courante."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status

from app.clock import get_now
from app.config import Settings, get_settings
from app.db import DbSession
from app.models.utilisateur import Utilisateur
from app.schemas.auth import (
    ConnexionEntree,
    CsrfSortie,
    InscriptionEtat,
    InscriptionSortie,
    SessionSortie,
    UtilisateurSession,
)
from app.schemas.utilisateur import InscriptionEntree
from app.security.csrf import generer_jeton, poser_cookie_csrf
from app.security.dependances import get_current_user
from app.security.jetons import poser_cookie_session
from app.services import auth as service_auth
from app.services import inscription as service_inscription

router = APIRouter(prefix="/auth", tags=["connexion"])


def _session(utilisateur: Utilisateur) -> SessionSortie:
    return SessionSortie(utilisateur=UtilisateurSession.model_validate(utilisateur))


@router.get("/csrf")
def jeton_csrf(
    request: Request, response: Response, settings: Settings = Depends(get_settings)
) -> CsrfSortie:
    """Renvoie le jeton CSRF du navigateur, en le créant s'il n'existe pas encore."""
    jeton = request.cookies.get(settings.csrf_cookie_name) or generer_jeton()
    poser_cookie_csrf(response, jeton, settings)
    response.headers["Cache-Control"] = "no-store"
    return CsrfSortie(jeton=jeton)


@router.post("/login")
def connexion(
    entree: ConnexionEntree,
    response: Response,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> SessionSortie:
    utilisateur = service_auth.connecter(
        db, entree.email, entree.mot_de_passe, maintenant, settings
    )
    poser_cookie_session(response, utilisateur, maintenant, settings)
    return _session(utilisateur)


@router.get("/inscription")
def etat_inscription(db: DbSession, response: Response) -> InscriptionEtat:
    """Public : la prochaine inscription crée-t-elle le premier compte du garage ?"""
    response.headers["Cache-Control"] = "no-store"
    return InscriptionEtat(premier_compte=not service_inscription.gerant_actif_existe(db))


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    responses={201: {"model": InscriptionSortie, "description": "Premier compte du garage"}},
)
def inscription(
    entree: InscriptionEntree,
    response: Response,
    db: DbSession,
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> InscriptionSortie:
    """Inscription autonome (story S8.3) : 201 et session pour le premier compte du garage,
    sinon 202 et le même message, que l'e-mail soit déjà connu ou non."""
    utilisateur = service_inscription.inscrire(db, entree, maintenant, settings)
    if utilisateur is None:
        return InscriptionSortie(
            compte_actif=False,
            message=service_inscription.MESSAGE_DEMANDE_ENREGISTREE,
            utilisateur=None,
        )
    response.status_code = status.HTTP_201_CREATED
    poser_cookie_session(response, utilisateur, maintenant, settings)
    return InscriptionSortie(
        compte_actif=True,
        message=service_inscription.MESSAGE_PREMIER_COMPTE,
        utilisateur=UtilisateurSession.model_validate(utilisateur),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def deconnexion(response: Response, settings: Settings = Depends(get_settings)) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.get("/me")
def session_courante(utilisateur: Utilisateur = Depends(get_current_user)) -> SessionSortie:
    return _session(utilisateur)
