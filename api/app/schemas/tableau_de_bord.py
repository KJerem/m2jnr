"""Schémas du tableau de bord du gérant."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.rendez_vous import RendezVous
from app.schemas.ordre import ClientOrdre, OrdreResume, PontSortie, VehiculeOrdre, resume_ordre
from app.services.tableau_de_bord import TableauDeBord


class IndicateursSortie(BaseModel):
    vehicules_atelier: int
    entres_aujourdhui: int
    prets_a_restituer: int
    a_restituer_aujourdhui: int
    en_retard: int
    rendez_vous_aujourdhui: int
    prochain_rendez_vous: datetime | None
    facture_aujourdhui_ttc_centimes: int
    facture_semaine_derniere_ttc_centimes: int
    # Même jour de la semaine précédente, base de la variation.
    jour_comparaison: date
    # Arrondie à l'entier ; null si rien n'avait été facturé le jour de comparaison.
    variation_pct: int | None


class ArriveeSortie(BaseModel):
    rendez_vous_id: int
    heure: datetime
    fin: datetime
    motif: str
    pont: PontSortie
    vehicule: VehiculeOrdre
    client: ClientOrdre
    ordre_id: int | None


class ATraiterSortie(BaseModel):
    type: Literal["retard", "facture_a_etablir", "devis_a_valider", "non_affecte"]
    titre: str
    detail: str
    ordre_id: int
    numero: str


class TableauDeBordSortie(BaseModel):
    jour: date
    ponts_actifs: int
    mecaniciens_actifs: int
    kpis: IndicateursSortie
    interventions: list[OrdreResume]
    arrivees: list[ArriveeSortie]
    a_traiter: list[ATraiterSortie]


def _arrivee(rdv: RendezVous) -> ArriveeSortie:
    client = rdv.vehicule.client
    return ArriveeSortie(
        rendez_vous_id=rdv.id,
        heure=rdv.debut,
        fin=rdv.fin,
        motif=rdv.motif,
        pont=PontSortie.model_validate(rdv.pont),
        vehicule=VehiculeOrdre.model_validate(rdv.vehicule),
        client=ClientOrdre(id=client.id, nom=client.nom, prenom=client.prenom),
        ordre_id=rdv.ordre.id if rdv.ordre else None,
    )


def sortie_tableau_de_bord(donnees: TableauDeBord, maintenant: datetime) -> TableauDeBordSortie:
    k = donnees.indicateurs
    return TableauDeBordSortie(
        jour=donnees.jour,
        ponts_actifs=donnees.ponts_actifs,
        mecaniciens_actifs=donnees.mecaniciens_actifs,
        kpis=IndicateursSortie(
            vehicules_atelier=k.vehicules_atelier,
            entres_aujourdhui=k.entres_aujourdhui,
            prets_a_restituer=k.prets_a_restituer,
            a_restituer_aujourdhui=k.a_restituer_aujourdhui,
            en_retard=k.en_retard,
            rendez_vous_aujourdhui=k.rendez_vous_aujourdhui,
            prochain_rendez_vous=k.prochain_rendez_vous,
            facture_aujourdhui_ttc_centimes=k.facture_aujourdhui_ttc_centimes,
            facture_semaine_derniere_ttc_centimes=k.facture_semaine_derniere_ttc_centimes,
            jour_comparaison=k.jour_comparaison,
            variation_pct=k.variation_pct,
        ),
        interventions=[
            resume_ordre(o, maintenant, voir_contact=True) for o in donnees.interventions
        ],
        arrivees=[_arrivee(r) for r in donnees.arrivees],
        a_traiter=[
            ATraiterSortie(
                type=a.type, titre=a.titre, detail=a.detail, ordre_id=a.ordre_id, numero=a.numero
            )
            for a in donnees.a_traiter
        ],
    )
