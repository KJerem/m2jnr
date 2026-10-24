"""Délais de l'atelier : retard sur l'heure de restitution promise au client."""

from datetime import datetime

from app.models.ordre_travail import StatutOT

# Un véhicule prêt (ou livré) n'est plus en retard, même si l'heure promise est passée.
STATUTS_EN_ATELIER = frozenset({StatutOT.A_FAIRE, StatutOT.EN_COURS})


def est_en_retard(
    statut: StatutOT, restitution_prevue: datetime | None, maintenant: datetime
) -> bool:
    """Vrai si l'heure de restitution promise est dépassée et que le véhicule n'est pas prêt."""
    return (
        restitution_prevue is not None
        and statut in STATUTS_EN_ATELIER
        and restitution_prevue < maintenant
    )
