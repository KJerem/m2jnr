"""Agrégat véhicule : toujours rattaché à un client existant, identifié par sa plaque."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.client import Client

# Format SIV : lettres sans I, O ni U ; bloc central différent de 000.
REGEX_IMMATRICULATION_SQL = "^[A-HJ-NP-TV-Z]{2}-[0-9]{3}-[A-HJ-NP-TV-Z]{2}$"
# VIN : 17 caractères, sans I, O ni Q.
REGEX_VIN_SQL = "^[A-HJ-NPR-Z0-9]{17}$"


class Vehicule(TimestampMixin, Base):
    __tablename__ = "vehicule"
    __table_args__ = (
        CheckConstraint(
            f"immatriculation ~ '{REGEX_IMMATRICULATION_SQL}' "
            "AND substr(immatriculation, 4, 3) <> '000'",
            name="immatriculation_siv",
        ),
        CheckConstraint("kilometrage >= 0", name="kilometrage_positif"),
        CheckConstraint(f"vin IS NULL OR vin ~ '{REGEX_VIN_SQL}'", name="vin_format"),
        CheckConstraint("char_length(btrim(marque)) > 0", name="marque_non_vide"),
        CheckConstraint("char_length(btrim(modele)) > 0", name="modele_non_vide"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("client.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    immatriculation: Mapped[str] = mapped_column(String(9), unique=True, nullable=False)
    marque: Mapped[str] = mapped_column(String(50), nullable=False)
    modele: Mapped[str] = mapped_column(String(80), nullable=False)
    kilometrage: Mapped[int] = mapped_column(Integer, nullable=False)
    vin: Mapped[str | None] = mapped_column(String(17))
    date_mise_en_circulation: Mapped[date | None] = mapped_column(Date)

    client: Mapped["Client"] = relationship(back_populates="vehicules")

    def __repr__(self) -> str:
        return f"<Vehicule {self.id} {self.immatriculation}>"
