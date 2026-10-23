"""Connexion, déconnexion et session courante."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.clock import get_now
from app.config import Settings, get_settings
from app.db import get_db
from app.models.utilisateur import Utilisateur
from app.schemas.auth import ConnexionEntree, CsrfSortie, SessionSortie, UtilisateurSortie
from app.security.csrf import generer_jeton, poser_cookie_csrf
from app.security.dependances import get_current_user
from app.security.jetons import creer_jeton_session
from app.services import auth as service_auth

router = APIRouter(prefix="/auth", tags=["connexion"])


def _session(utilisateur: Utilisateur) -> SessionSortie:
    return SessionSortie(utilisateur=UtilisateurSortie.model_validate(utilisateur))


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
    db: Session = Depends(get_db),
    maintenant: datetime = Depends(get_now),
    settings: Settings = Depends(get_settings),
) -> SessionSortie:
    utilisateur = service_auth.connecter(
        db, entree.email, entree.mot_de_passe, maintenant, settings
    )
    jeton = creer_jeton_session(utilisateur.id, utilisateur.role, maintenant, settings)
    response.set_cookie(
        settings.session_cookie_name,
        jeton,
        max_age=settings.session_duration_minutes * 60,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return _session(utilisateur)


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
