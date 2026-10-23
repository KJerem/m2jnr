"""Modèles SQLAlchemy. Chaque agrégat est importé ici pour qu'Alembic le détecte."""

from app.db import Base

__all__ = ["Base"]
