"""Protection CSRF par « double-submit cookie ».

Le serveur dépose un jeton aléatoire dans un cookie lisible par le JavaScript de la même origine
(non httpOnly). Toute requête qui modifie des données (POST, PUT, PATCH, DELETE), connexion
comprise, doit recopier ce jeton dans l'en-tête `X-CSRF-Token`. Un site tiers peut faire envoyer
le cookie par le navigateur, mais ne peut pas le lire : il ne peut donc pas fournir l'en-tête.
"""

import hmac
import secrets

from fastapi import status
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings

METHODES_SURES = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
MESSAGE_CSRF = "Jeton de sécurité manquant ou invalide. Rechargez la page."


def generer_jeton() -> str:
    """32 octets aléatoires encodés en base64 url."""
    return secrets.token_urlsafe(32)


def jetons_concordent(cookie: str | None, entete: str | None) -> bool:
    if not cookie or not entete:
        return False
    return hmac.compare_digest(cookie.encode(), entete.encode())


def poser_cookie_csrf(response: Response, jeton: str, settings: Settings) -> None:
    response.set_cookie(
        settings.csrf_cookie_name,
        jeton,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
    )


class CsrfMiddleware:
    """Middleware ASGI : refuse en 403 `csrf_invalide` une méthode non sûre sans jeton valide."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in METHODES_SURES:
            await self.app(scope, receive, send)
            return
        requete = Request(scope)
        cookie = requete.cookies.get(self.settings.csrf_cookie_name)
        entete = requete.headers.get(self.settings.csrf_header_name)
        if not jetons_concordent(cookie, entete):
            refus = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"code": "csrf_invalide", "message": MESSAGE_CSRF, "champs": {}},
            )
            await refus(scope, receive, send)
            return
        await self.app(scope, receive, send)
