"""Compteurs de numérotation (ordres de travail, factures) : une ligne par type et par année.

La ligne est verrouillée (SELECT … FOR UPDATE) dans la transaction qui crée le document : deux
créations simultanées obtiennent deux numéros consécutifs, et une annulation annule aussi
l'incrément (aucun trou). Voir app/services/numerotation.py.
"""

from sqlalchemy import CheckConstraint, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Compteur(Base):
    __tablename__ = "compteur"
    __table_args__ = (CheckConstraint("dernier >= 0", name="dernier_positif"),)

    type: Mapped[str] = mapped_column(String(20), primary_key=True)
    annee: Mapped[int] = mapped_column(Integer, primary_key=True)
    dernier: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    def __repr__(self) -> str:
        return f"<Compteur {self.type} {self.annee} {self.dernier}>"
