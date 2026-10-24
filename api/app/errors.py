"""Format d'erreur unique de l'API : {"code", "message", "champs"}.

Le front affiche `message` tel quel ; `champs` associe un nom de champ à son erreur.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Erreur métier attendue, traduite en réponse JSON propre."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        champs: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.champs = champs or {}
        self.details = details or {}


def not_found(message: str = "Ressource introuvable.") -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "introuvable", message)


def conflict(code: str, message: str, **details: Any) -> AppError:
    return AppError(status.HTTP_409_CONFLICT, code, message, details=details)


def invalid(champ: str, message: str) -> AppError:
    return AppError(
        status.HTTP_422_UNPROCESSABLE_CONTENT, "validation", message, champs={champ: message}
    )


def forbidden(message: str = "Accès refusé pour votre rôle.") -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "interdit", message)


def _body(
    code: str, message: str, champs: dict[str, str] | None = None, **extra: Any
) -> dict[str, Any]:
    return {"code": code, "message": message, "champs": champs or {}, **extra}


_HTTP_MESSAGES = {
    401: ("non_authentifie", "Veuillez vous connecter."),
    403: ("interdit", "Accès refusé."),
    404: ("introuvable", "Ressource introuvable."),
    405: ("methode_non_autorisee", "Méthode non autorisée."),
}


def _champ_depuis_loc(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "requete"


def _traduire(err: dict[str, Any]) -> str:
    typ = err.get("type", "")
    ctx = err.get("ctx") or {}
    if typ == "missing" or (typ == "string_type" and err.get("input") is None):
        return "Champ obligatoire."
    if typ in ("string_too_short",) and ctx.get("min_length") == 1:
        return "Champ obligatoire."
    if typ == "value_error":
        # Les validateurs métier lèvent ValueError avec un message déjà en français.
        return str(ctx.get("error", err.get("msg", "Valeur invalide.")))
    if typ in ("int_parsing", "int_type", "int_from_float"):
        return "Nombre entier attendu."
    if typ in ("float_parsing", "float_type", "decimal_parsing", "decimal_type"):
        return "Nombre attendu."
    egal = " ou égal" if "equal" in typ else ""
    if typ.startswith("greater_than"):
        return f"Doit être supérieur{egal} à {ctx.get('ge', ctx.get('gt'))}."
    if typ.startswith("less_than"):
        return f"Doit être inférieur{egal} à {ctx.get('le', ctx.get('lt'))}."
    if typ == "string_too_long":
        return f"{ctx.get('max_length')} caractères maximum."
    if typ == "string_too_short":
        return f"{ctx.get('min_length')} caractères minimum."
    if typ.startswith(("date", "datetime")):
        return "Date invalide."
    if typ == "enum" or typ == "literal_error":
        return "Valeur non autorisée."
    if typ == "value_error.email" or "email" in str(err.get("msg", "")).lower():
        return "Adresse e-mail invalide."
    return str(err.get("msg", "Valeur invalide."))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.champs, **exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        champs: dict[str, str] = {}
        for err in exc.errors():
            champs.setdefault(_champ_depuis_loc(tuple(err.get("loc", ()))), _traduire(err))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_body("validation", "Certains champs sont invalides.", champs),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_MESSAGES.get(exc.status_code, ("erreur", "Erreur."))
        if isinstance(exc.detail, str) and exc.detail and exc.detail not in ("Not Found",):
            message = exc.detail
        return JSONResponse(status_code=exc.status_code, content=_body(code, message))
