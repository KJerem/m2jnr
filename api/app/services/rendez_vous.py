"""Rendez-vous sur les ponts de l'atelier et planning du jour.

Règles (story S2.1) :
- véhicule, pont, début, durée et motif obligatoires ; durée de 1 minute à 10 heures ;
- pas de rendez-vous dans le passé (horloge injectée) ;
- pas de chevauchement sur un même pont : le service cherche le créneau en conflit pour un
  message clair (« Le Pont 1 est déjà occupé de 9 h 00 à 10 h 30. »), et la contrainte
  EXCLUDE de la base arrête deux prises simultanées (409 aussi) ;
- les créneaux sont semi-ouverts [début, fin[ : un rendez-vous peut commencer à l'heure
  exacte où le précédent finit ; un autre pont reste libre ;
- un rendez-vous donne lieu à au plus un ordre de travail.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from fastapi import status
from psycopg import errors as erreurs_pg
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.clock import bornes_jour
from app.db import id_possible
from app.errors import AppError, conflict, invalid, not_found
from app.models.ordre_travail import OrdreTravail, StatutOT
from app.models.pont import Pont
from app.models.rendez_vous import RendezVous
from app.models.utilisateur import Utilisateur
from app.models.vehicule import Vehicule
from app.schemas.ordre import OrdreEntree
from app.schemas.rendez_vous import RendezVousEntree
from app.services import ordres as service_ordres
from app.services.format import formater_heure

MESSAGE_PASSE = "Impossible de prendre un rendez-vous dans le passé."
MESSAGE_PONT_INVALIDE = "Choisissez un pont de l'atelier."
MESSAGE_RENDEZ_VOUS_INTROUVABLE = "Rendez-vous introuvable."
MESSAGE_ORDRE_EXISTANT = "Un ordre de travail est déjà ouvert pour ce rendez-vous."
LIMITE_LISTE = 500

CHARGEMENT_RENDEZ_VOUS: tuple[ExecutableOption, ...] = (
    selectinload(RendezVous.vehicule).selectinload(Vehicule.client),
    selectinload(RendezVous.pont),
    selectinload(RendezVous.ordre).options(*service_ordres.CHARGEMENT_ORDRE),
)


def lister_ponts(db: Session) -> list[Pont]:
    return list(db.scalars(select(Pont).where(Pont.actif.is_(True)).order_by(Pont.nom, Pont.id)))


def _pont_actif(db: Session, pont_id: int) -> Pont:
    pont = db.get(Pont, pont_id) if id_possible(pont_id) else None
    if pont is None or not pont.actif:
        raise invalid("pont_id", MESSAGE_PONT_INVALIDE)
    return pont


def _vehicule(db: Session, vehicule_id: int) -> Vehicule:
    vehicule = db.get(Vehicule, vehicule_id) if id_possible(vehicule_id) else None
    if vehicule is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            "introuvable",
            "Véhicule introuvable.",
            champs={"vehicule_id": "Véhicule introuvable."},
        )
    return vehicule


def message_creneau_occupe(pont: Pont, occupant: RendezVous, fuseau: str) -> str:
    debut = formater_heure(occupant.debut, fuseau)
    fin = formater_heure(occupant.fin, fuseau)
    return f"Le {pont.nom} est déjà occupé de {debut} à {fin}."


def creneau_en_conflit(
    db: Session, pont_id: int, debut: datetime, fin: datetime
) -> RendezVous | None:
    """Premier rendez-vous du pont qui chevauche [début, fin[ (bornes semi-ouvertes)."""
    return db.scalars(
        select(RendezVous)
        .where(RendezVous.pont_id == pont_id, RendezVous.debut < fin, RendezVous.fin > debut)
        .order_by(RendezVous.debut, RendezVous.id)
        .limit(1)
    ).first()


def _creneau_occupe(pont: Pont, occupant: RendezVous | None, fuseau: str) -> AppError:
    if occupant is None:
        return conflict("creneau_occupe", f"Le {pont.nom} est déjà occupé sur ce créneau.")
    return conflict(
        "creneau_occupe",
        message_creneau_occupe(pont, occupant, fuseau),
        rendez_vous_id=occupant.id,
    )


def creer_rendez_vous(
    db: Session,
    entree: RendezVousEntree,
    auteur: Utilisateur,
    maintenant: datetime,
    fuseau: str,
) -> RendezVous:
    vehicule = _vehicule(db, entree.vehicule_id)
    pont = _pont_actif(db, entree.pont_id)
    if entree.debut < maintenant:
        raise invalid("debut", MESSAGE_PASSE)
    fin = entree.debut + timedelta(minutes=entree.duree_minutes)
    occupant = creneau_en_conflit(db, pont.id, entree.debut, fin)
    if occupant is not None:
        raise _creneau_occupe(pont, occupant, fuseau)

    rdv = RendezVous(
        vehicule=vehicule,
        pont=pont,
        debut=entree.debut,
        duree_minutes=entree.duree_minutes,
        motif=entree.motif,
        createur=auteur,
    )
    try:
        # Point de sauvegarde : si une prise simultanée a pris le créneau entre la
        # vérification et l'insertion, la contrainte EXCLUDE refuse la ligne ; seule cette
        # insertion est annulée et la réponse reste un 409 clair.
        with db.begin_nested():
            db.add(rdv)
            db.flush()
    except IntegrityError as exc:
        if not isinstance(exc.orig, erreurs_pg.ExclusionViolation):
            raise
        raise _creneau_occupe(
            pont, creneau_en_conflit(db, pont.id, entree.debut, fin), fuseau
        ) from exc
    db.refresh(rdv)
    return rdv


def obtenir_rendez_vous(db: Session, rdv_id: int, *, verrouiller: bool = False) -> RendezVous:
    rdv = None
    if id_possible(rdv_id):
        requete = select(RendezVous).where(RendezVous.id == rdv_id)
        if verrouiller:
            requete = requete.with_for_update().execution_options(populate_existing=True)
        rdv = db.scalars(requete.options(*CHARGEMENT_RENDEZ_VOUS)).one_or_none()
    if rdv is None:
        raise not_found(MESSAGE_RENDEZ_VOUS_INTROUVABLE)
    return rdv


def lister_rendez_vous(
    db: Session, depuis: datetime, avant: datetime | None, pont_id: int | None
) -> list[RendezVous]:
    """Rendez-vous commençant dans [depuis, avant[, triés par heure de début."""
    requete = select(RendezVous).where(RendezVous.debut >= depuis)
    if avant is not None:
        requete = requete.where(RendezVous.debut < avant)
    if pont_id is not None:
        requete = requete.where(RendezVous.pont_id == pont_id)
    return list(
        db.scalars(
            requete.options(*CHARGEMENT_RENDEZ_VOUS)
            .order_by(RendezVous.debut, RendezVous.pont_id, RendezVous.id)
            .limit(LIMITE_LISTE)
        )
    )


def ouvrir_ordre(
    db: Session, rdv: RendezVous, auteur: Utilisateur, maintenant: datetime, annee: int
) -> OrdreTravail:
    """Ouvre l'OT du rendez-vous (véhicule, motif → demande du client). L'appelant a
    verrouillé le rendez-vous : deux clics simultanés n'ouvrent pas deux OT."""
    if rdv.ordre is not None:
        raise conflict("ordre_existant", MESSAGE_ORDRE_EXISTANT, ordre_id=rdv.ordre.id)
    entree = OrdreEntree.model_validate(
        {"vehicule_id": rdv.vehicule_id, "demande_client": rdv.motif}
    )
    ordre = service_ordres.creer_ordre(db, entree, auteur, maintenant, annee)
    ordre.rendez_vous = rdv
    db.flush()
    return ordre


def minutes_restantes(ordre: OrdreTravail) -> int:
    """Durée prévue des tâches pas encore terminées."""
    return sum(t.duree_prevue_minutes for t in ordre.taches if not t.terminee)


@dataclass(frozen=True)
class PontDuJour:
    pont: Pont
    rendez_vous: list[RendezVous]
    # Rendez-vous d'un jour précédent dont l'OT n'est pas livré : le véhicule occupe encore
    # le pont. Affichés en tête de colonne, ils pèsent le temps des tâches restantes.
    reports: list[RendezVous] = field(default_factory=list)

    @property
    def charge_minutes(self) -> int:
        restantes = sum(minutes_restantes(r.ordre) for r in self.reports if r.ordre)
        return restantes + sum(r.duree_minutes for r in self.rendez_vous)


@dataclass(frozen=True)
class Planning:
    jour: date
    # Minuit du jour à Paris, en UTC : heure affichée des reports.
    debut: datetime
    ponts: list[PontDuJour]
    a_planifier: list[OrdreTravail]


def rendez_vous_reportes(db: Session, avant: datetime) -> list[RendezVous]:
    """Rendez-vous commencés avant `avant` dont l'OT ouvert n'est pas encore livré."""
    return list(
        db.scalars(
            select(RendezVous)
            .join(RendezVous.ordre)
            .where(RendezVous.debut < avant, OrdreTravail.statut != StatutOT.LIVRE)
            .options(*CHARGEMENT_RENDEZ_VOUS)
            .order_by(RendezVous.debut, RendezVous.id)
            .limit(LIMITE_LISTE)
        )
    )


def planning_du_jour(db: Session, jour: date, fuseau: str) -> Planning:
    """Rendez-vous du jour de Paris (un rendez-vous à 23 h 30 appartient à ce jour) groupés
    par pont, précédés des OT non livrés dont le rendez-vous date d'un jour précédent
    (le véhicule est encore sur le pont), et OT non livrés sans rendez-vous (« À planifier »)."""
    debut, fin = bornes_jour(jour, fuseau)
    rendez_vous = lister_rendez_vous(db, debut, fin, None)
    reports = rendez_vous_reportes(db, debut)
    ponts = [
        PontDuJour(
            pont,
            [r for r in rendez_vous if r.pont_id == pont.id],
            [r for r in reports if r.pont_id == pont.id],
        )
        for pont in lister_ponts(db)
    ]
    a_planifier = list(
        db.scalars(
            select(OrdreTravail)
            .where(OrdreTravail.rendez_vous_id.is_(None), OrdreTravail.statut != StatutOT.LIVRE)
            .options(*service_ordres.CHARGEMENT_ORDRE)
            .order_by(
                OrdreTravail.prioritaire.desc(),
                OrdreTravail.restitution_prevue.asc().nulls_last(),
                OrdreTravail.ouvert_le,
                OrdreTravail.id,
            )
        )
    )
    # Un pont retiré de l'atelier depuis le rendez-vous : l'OT reste visible, à replanifier.
    ponts_actifs = {p.pont.id for p in ponts}
    a_planifier += [r.ordre for r in reports if r.ordre and r.pont_id not in ponts_actifs]
    return Planning(jour=jour, debut=debut, ponts=ponts, a_planifier=a_planifier)
