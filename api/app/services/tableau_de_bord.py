"""Tableau de bord du gérant (maquette 4) : la journée de l'atelier en un écran.

« Aujourd'hui » est le jour de Paris de l'horloge injectée ; ses bornes [minuit, minuit du
lendemain[ sont calculées dans le fuseau du garage (journées de 23 ou 25 heures comprises).

- véhicules à l'atelier : OT non livrés, dont ceux ouverts aujourd'hui ;
- prêts à restituer : OT « Prêt », dont ceux promis pour aujourd'hui ;
- en retard : même règle que les cartes (heure promise dépassée, véhicule ni prêt ni livré) ;
- rendez-vous du jour et prochain à venir ;
- facturé aujourd'hui (TTC des factures émises dans la journée) et variation par rapport au
  même jour de la semaine précédente (null si rien n'avait été facturé ce jour-là) ;
- interventions du jour (mêmes OT que le kanban : non livrés et livrés aujourd'hui) :
  urgentes ou en retard d'abord, puis par heure de restitution, les livrées à la fin ;
- arrivées prévues : rendez-vous du jour qui commencent après maintenant ;
- à traiter : retards, factures à établir (devis accepté, non facturé, d'un OT « Prêt » ou
  « Livré »), devis à faire valider (envoyés au client, sans réponse), OT non livrés sans
  mécanicien ou dont le mécanicien a été désactivé (revue du sprint 5 : ils n'apparaissaient
  plus nulle part, le compte désactivé ne voyant plus ses travaux).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, selectinload

from app.clock import bornes_jour, date_locale
from app.models.devis import Devis, StatutDevis
from app.models.facture import Facture
from app.models.ordre_travail import OrdreTravail, StatutOT
from app.models.pont import Pont
from app.models.rendez_vous import RendezVous
from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.models.vehicule import Vehicule
from app.services import ordres as service_ordres
from app.services import rendez_vous as service_rendez_vous
from app.services.delais import est_en_retard
from app.services.format import (
    formater_date_courte,
    formater_duree,
    formater_euros,
    formater_heure,
)

INTERVENTIONS_MAX = 200
STATUTS_FACTURABLES = (StatutOT.TERMINE, StatutOT.LIVRE)

TypeATraiter = Literal[
    "retard", "facture_a_etablir", "devis_a_valider", "non_affecte", "compte_a_valider"
]


@dataclass(frozen=True)
class Indicateurs:
    vehicules_atelier: int
    entres_aujourdhui: int
    prets_a_restituer: int
    a_restituer_aujourdhui: int
    en_retard: int
    rendez_vous_aujourdhui: int
    prochain_rendez_vous: datetime | None
    facture_aujourdhui_ttc_centimes: int
    facture_semaine_derniere_ttc_centimes: int
    jour_comparaison: date
    variation_pct: int | None


@dataclass(frozen=True)
class ATraiter:
    """Élément de « À traiter maintenant » : lié à un OT (ordre_id, numero) ou, pour un
    compte à valider (story S8.3), à la fiche de l'employé (utilisateur_id)."""

    type: TypeATraiter
    titre: str
    detail: str
    ordre_id: int | None = None
    numero: str | None = None
    utilisateur_id: int | None = None


@dataclass(frozen=True)
class TableauDeBord:
    jour: date
    ponts_actifs: int
    mecaniciens_actifs: int
    indicateurs: Indicateurs
    interventions: list[OrdreTravail]
    arrivees: list[RendezVous]
    a_traiter: list[ATraiter]


def variation_pct(aujourdhui: int, reference: int) -> int | None:
    """Évolution en pour cent, arrondie à l'entier (demi vers le haut en valeur absolue) ;
    None si la référence est nulle (pas de pourcentage sur zéro)."""
    if reference <= 0:
        return None
    pct = Decimal(aujourdhui - reference) * 100 / Decimal(reference)
    return int(pct.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def trier_interventions(ordres: Sequence[OrdreTravail], maintenant: datetime) -> list[OrdreTravail]:
    """Urgentes ou en retard d'abord, puis par heure de restitution (sans heure à la fin) ;
    les OT livrés ferment la liste, dans l'ordre de leur livraison."""
    fin_des_temps = datetime.max.replace(tzinfo=maintenant.tzinfo)

    def cle(ordre: OrdreTravail) -> tuple[int, datetime, datetime, int]:
        if ordre.statut == StatutOT.LIVRE:
            return (2, ordre.cloture_le or fin_des_temps, ordre.ouvert_le, ordre.id)
        prioritaire = ordre.prioritaire or est_en_retard(
            ordre.statut, ordre.restitution_prevue, maintenant
        )
        return (
            0 if prioritaire else 1,
            ordre.restitution_prevue or fin_des_temps,
            ordre.ouvert_le,
            ordre.id,
        )

    return sorted(ordres, key=cle)


def _compter(db: Session, *conditions: ColumnElement[bool]) -> int:
    """Nombre d'OT qui remplissent toutes les conditions."""
    return int(db.scalar(select(func.count(OrdreTravail.id)).where(*conditions)) or 0)


def total_facture_entre(db: Session, depuis: datetime, avant: datetime) -> int:
    """Somme des TTC des factures émises dans [depuis, avant[."""
    return int(
        db.scalar(
            select(func.coalesce(func.sum(Facture.total_ttc_centimes), 0)).where(
                Facture.emise_le >= depuis, Facture.emise_le < avant
            )
        )
        or 0
    )


def _nom(ordre: OrdreTravail) -> str:
    client = ordre.vehicule.client
    return " ".join(part for part in (client.prenom, client.nom) if part)


def _vehicule(ordre: OrdreTravail) -> str:
    return f"{ordre.vehicule.marque} {ordre.vehicule.modele}"


def formater_retard(minutes: int) -> str:
    """« 40 min », « 2 h 40 », au-delà d'une journée « 1 j 3 h »."""
    if minutes < 24 * 60:
        return formater_duree(minutes)
    jours, reste = divmod(minutes, 24 * 60)
    return f"{jours} j {reste // 60} h"


def _promesse(restitution: datetime, jour: date, fuseau: str) -> str:
    heure = formater_heure(restitution, fuseau)
    jour_promis = date_locale(restitution, fuseau)
    return (
        f"promis à {heure}"
        if jour_promis == jour
        else f"promis le {formater_date_courte(jour_promis)} à {heure}"
    )


def _retards(
    ordres: Sequence[OrdreTravail], maintenant: datetime, jour: date, fuseau: str
) -> list[ATraiter]:
    elements = []
    for ordre in ordres:
        restitution = ordre.restitution_prevue
        if restitution is None or not est_en_retard(ordre.statut, restitution, maintenant):
            continue
        retard = int((maintenant - restitution).total_seconds() // 60)
        elements.append(
            ATraiter(
                type="retard",
                titre=f"{_nom(ordre)} attend",
                detail=(
                    f"{_vehicule(ordre)} · {ordre.numero} · {_promesse(restitution, jour, fuseau)},"
                    f" retard de {formater_retard(retard)}"
                ),
                ordre_id=ordre.id,
                numero=ordre.numero,
            )
        )
    return elements


CHARGEMENT_DEVIS_ORDRE = (
    selectinload(Devis.ordre).selectinload(OrdreTravail.vehicule).selectinload(Vehicule.client),
)


def devis_a_facturer(db: Session) -> list[Devis]:
    """Devis acceptés et non facturés d'un OT « Prêt » ou « Livré » (story S4.2 : seul un
    devis accepté se facture), en une requête (et leurs OT, véhicules et clients en trois
    autres)."""
    return list(
        db.scalars(
            select(Devis)
            .join(Devis.ordre)
            .outerjoin(Facture, Facture.devis_id == Devis.id)
            .where(
                Facture.id.is_(None),
                Devis.statut == StatutDevis.ACCEPTE,
                OrdreTravail.statut.in_(STATUTS_FACTURABLES),
            )
            .options(*CHARGEMENT_DEVIS_ORDRE)
            .order_by(OrdreTravail.cloture_le.asc().nulls_first(), Devis.id)
        )
    )


def devis_a_valider(db: Session) -> list[Devis]:
    """Devis envoyés au client et encore sans réponse, du plus ancien envoi au plus récent."""
    return list(
        db.scalars(
            select(Devis)
            .where(Devis.statut == StatutDevis.ENVOYE)
            .options(*CHARGEMENT_DEVIS_ORDRE)
            .order_by(Devis.envoye_le, Devis.id)
        )
    )


def _factures_a_etablir(devis: Sequence[Devis]) -> list[ATraiter]:
    return [
        ATraiter(
            type="facture_a_etablir",
            titre="Facture à établir",
            detail=(
                f"{_nom(d.ordre)} · {_vehicule(d.ordre)} · {d.ordre.numero}"
                f" · {formater_euros(d.total_ttc_centimes)} TTC"
            ),
            ordre_id=d.ordre.id,
            numero=d.ordre.numero,
        )
        for d in devis
    ]


def _envoi(envoye_le: datetime, jour: date, fuseau: str) -> str:
    """« envoyé à 11 h 05 » aujourd'hui, « envoyé le ven. 23 oct. à 11 h 05 » sinon."""
    heure = formater_heure(envoye_le, fuseau)
    jour_envoi = date_locale(envoye_le, fuseau)
    if jour_envoi == jour:
        return f"envoyé à {heure}"
    return f"envoyé le {formater_date_courte(jour_envoi)} à {heure}"


def _devis_a_valider(devis: Sequence[Devis], jour: date, fuseau: str) -> list[ATraiter]:
    return [
        ATraiter(
            type="devis_a_valider",
            titre="Devis à faire valider",
            detail=(
                f"{_nom(d.ordre)} · {_vehicule(d.ordre)} · {formater_euros(d.total_ttc_centimes)}"
                f" TTC {_envoi(d.envoye_le, jour, fuseau)}"
                if d.envoye_le
                else f"{_nom(d.ordre)} · {_vehicule(d.ordre)}"
            ),
            ordre_id=d.ordre.id,
            numero=d.ordre.numero,
        )
        for d in devis
    ]


def mecanicien_a_affecter(ordre: OrdreTravail) -> bool:
    """Vrai pour un OT non livré sans mécanicien, ou dont le mécanicien n'est plus actif
    (compte désactivé : il ne voit plus ses travaux, un autre doit les reprendre)."""
    if ordre.statut == StatutOT.LIVRE:
        return False
    return ordre.mecanicien is None or not ordre.mecanicien.actif


def _non_affectes(ordres: Sequence[OrdreTravail]) -> list[ATraiter]:
    return [
        ATraiter(
            type="non_affecte",
            titre="Mécanicien à affecter",
            detail=(
                f"{_vehicule(o)} · {o.numero} · {_nom(o)}"
                if o.mecanicien is None
                else f"{_vehicule(o)} · {o.numero} · {_nom(o)} · compte de"
                f" {o.mecanicien.nom_affiche} désactivé"
            ),
            ordre_id=o.id,
            numero=o.numero,
        )
        for o in ordres
        if mecanicien_a_affecter(o)
    ]


def comptes_a_valider(db: Session) -> list[Utilisateur]:
    """Inscriptions en attente de validation (story S8.3), de la plus ancienne à la plus récente."""
    return list(
        db.scalars(
            select(Utilisateur)
            .where(Utilisateur.statut == StatutCompte.EN_ATTENTE)
            .order_by(Utilisateur.cree_le, Utilisateur.id)
        )
    )


def _comptes_a_valider(comptes: Sequence[Utilisateur]) -> list[ATraiter]:
    return [
        ATraiter(
            type="compte_a_valider",
            titre="Compte à valider",
            detail=f"{u.nom_affiche} · {u.email}",
            utilisateur_id=u.id,
        )
        for u in comptes
    ]


def tableau_de_bord(db: Session, maintenant: datetime, fuseau: str) -> TableauDeBord:
    jour = date_locale(maintenant, fuseau)
    debut, fin = bornes_jour(jour, fuseau)
    jour_comparaison = jour - timedelta(days=7)
    debut_comparaison, fin_comparaison = bornes_jour(jour_comparaison, fuseau)

    interventions = trier_interventions(
        service_ordres.lister_ordres(
            db, service_ordres.FiltresOrdres(livres_depuis=debut), 1, INTERVENTIONS_MAX
        ).elements,
        maintenant,
    )
    non_livre = OrdreTravail.statut != StatutOT.LIVRE
    rendez_vous_du_jour = select(func.count(RendezVous.id)).where(
        RendezVous.debut >= debut, RendezVous.debut < fin
    )
    facture_aujourdhui = total_facture_entre(db, debut, fin)
    facture_reference = total_facture_entre(db, debut_comparaison, fin_comparaison)
    indicateurs = Indicateurs(
        vehicules_atelier=_compter(db, non_livre),
        entres_aujourdhui=_compter(
            db, OrdreTravail.ouvert_le >= debut, OrdreTravail.ouvert_le < fin
        ),
        prets_a_restituer=_compter(db, OrdreTravail.statut == StatutOT.TERMINE),
        a_restituer_aujourdhui=_compter(
            db,
            OrdreTravail.statut == StatutOT.TERMINE,
            OrdreTravail.restitution_prevue >= debut,
            OrdreTravail.restitution_prevue < fin,
        ),
        en_retard=_compter(
            db,
            OrdreTravail.statut.in_((StatutOT.A_FAIRE, StatutOT.EN_COURS)),
            OrdreTravail.restitution_prevue < maintenant,
        ),
        rendez_vous_aujourdhui=int(db.scalar(rendez_vous_du_jour) or 0),
        prochain_rendez_vous=db.scalar(
            select(func.min(RendezVous.debut)).where(
                RendezVous.debut >= maintenant, RendezVous.debut < fin
            )
        ),
        facture_aujourdhui_ttc_centimes=facture_aujourdhui,
        facture_semaine_derniere_ttc_centimes=facture_reference,
        jour_comparaison=jour_comparaison,
        variation_pct=variation_pct(facture_aujourdhui, facture_reference),
    )
    # Rendez-vous du jour qui commencent après maintenant (strictement).
    arrivees = [
        r
        for r in service_rendez_vous.lister_rendez_vous(db, maintenant, fin, None)
        if r.debut > maintenant
    ]
    a_traiter = (
        _retards(interventions, maintenant, jour, fuseau)
        + _factures_a_etablir(devis_a_facturer(db))
        + _devis_a_valider(devis_a_valider(db), jour, fuseau)
        + _non_affectes(interventions)
        + _comptes_a_valider(comptes_a_valider(db))
    )
    return TableauDeBord(
        jour=jour,
        ponts_actifs=int(db.scalar(select(func.count(Pont.id)).where(Pont.actif.is_(True))) or 0),
        mecaniciens_actifs=int(
            db.scalar(
                select(func.count(Utilisateur.id)).where(
                    Utilisateur.role == Role.MECANICIEN,
                    Utilisateur.statut == StatutCompte.ACTIF,
                )
            )
            or 0
        ),
        indicateurs=indicateurs,
        interventions=interventions,
        arrivees=arrivees,
        a_traiter=a_traiter,
    )
