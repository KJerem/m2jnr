"""Point d'entrée FastAPI de l'API Établi."""

from fastapi import FastAPI

from app.config import get_settings
from app.errors import register_error_handlers
from app.routers import auth, clients, devis, factures, health
from app.security.csrf import CsrfMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Établi — API de gestion de garage",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    register_error_handlers(app)
    app.add_middleware(CsrfMiddleware, settings=settings)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(clients.router)
    app.include_router(devis.router)
    app.include_router(factures.router)
    return app


app = create_app()
