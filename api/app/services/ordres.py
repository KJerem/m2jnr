"""Ordres de travail : ouverture, modification, consultation et liste.

Règles (story S3.1) :
- un OT est toujours rattaché à un véhicule existant ;
- son numéro « OT-AAAA-nnn » est attribué dans la transaction d'insertion (sans trou) ;
- le mécanicien affecté, s'il y en a un, est un mécanicien actif ;
- le kilométrage d'entrée ne peut pas être inférieur à celui du véhicule ; s'il est
  supérieur, la fiche du véhicule est mise à jour ;
- un OT livré n'est plus modifiable ; un OT « Prêt » ne reçoit plus de nouvelle tâche ;
- l'ouverture est la première ligne de l'historique des statuts (NULL → a_faire).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import id_possible
from app.errors import AppError, conflict, invalid, not_found
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT, TacheOT
from app.models.rendez_vous import RendezVous
from app.models.utilisateur import Role, Utilisateur
from app.models.vehicule import Vehicule
from app.schemas.ordre import (
    MESSAGE_VEHICULE_OBLIGATOIRE,
    OrdreEntree,
    OrdreModification,
    TacheModification,
)
from app.services.format import formater_km
from app.services.numerotation import TYPE_ORDRE_TRAVAIL, prochain_numero
from app.services.transitions import (
    MESSAGE_ORDRE_LIVRE,
    MESSAGE_ORDRE_PRET,
    MESSAGE_TACHE_INTROUVABLE,
    tracer,
)

MESSAGE_ORDRE_INTROUVABLE = "Ordre de travail introuvable."
MESSAGE_MECANICIEN_INVALIDE = "Choisissez un mécanicien actif."

# Tout ce qu'une carte ou une fiche d'OT affiche, chargé en quelques requêtes (pas de N+1).
CHARGEMENT_ORDRE = (
    selectinload(OrdreTravail.vehicule).selectinload(Vehicule.client),
    selectinload(OrdreTravail.mecanicien),
    selectinload(OrdreTravail.createur),
    selectinload(OrdreTravail.taches).selectinload(TacheOT.terminee_par_utilisateur),
    selectinload(OrdreTravail.historique).selectinload(HistoriqueStatut.utilisateur),
    selectinload(OrdreTravail.rendez_vous).selectinload(RendezVous.pont),
)


def message_kilometrage_inferieur(kilometrage_vehicule: int) -> str:
    return (
        "Le kilométrage d'entrée ne peut pas être inférieur à celui du véhicule "
        f"({formater_km(kilometrage_vehicule)})."
    )


def obtenir_ordre(db: Session, ordre_id: int, *, verrouiller: bool = False) -> OrdreTravail:
    """OT et tout ce qu'il affiche ; `verrouiller` pose SELECT … FOR UPDATE sur la ligne de
    l'OT : deux changements simultanés (statut, tâches) s'appliquent l'un après l'autre."""
    ordre = None
    if id_possible(ordre_id):
        requete = select(OrdreTravail).where(OrdreTravail.id == ordre_id)
        if verrouiller:
            requete = requete.with_for_update().execution_options(populate_existing=True)
        ordre = db.scalars(requete.options(*CHARGEMENT_ORDRE)).one_or_none()
    if ordre is None:
        raise not_found(MESSAGE_ORDRE_INTROUVABLE)
    return ordre


def vehicule_de_l_ordre(
    db: Session, vehicule_id: int | None, *, verrouiller: bool = False
) -> Vehicule:
    """Véhicule obligatoire : absent → 422, inconnu → 404 (même message, sur le champ).

    `verrouiller` pose SELECT … FOR UPDATE et relit la ligne validée : deux ouvertures
    simultanées qui relèvent le compteur comparent l'une après l'autre (pas de recul)."""
    if vehicule_id is None:
        raise invalid("vehicule_id", MESSAGE_VEHICULE_OBLIGATOIRE)
    vehicule = (
        db.get(Vehicule, vehicule_id, with_for_update=verrouiller, populate_existing=verrouiller)
        if id_possible(vehicule_id)
        else None
    )
    if vehicule is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            "introuvable",
            MESSAGE_VEHICULE_OBLIGATOIRE,
            champs={"vehicule_id": "Véhicule introuvable."},
        )
    return vehicule


def mecanicien_actif(db: Session, mecanicien_id: int | None) -> Utilisateur | None:
    if mecanicien_id is None:
        return None
    utilisateur = db.get(Utilisateur, mecanicien_id) if id_possible(mecanicien_id) else None
    if utilisateur is None or utilisateur.role != Role.MECANICIEN or not utilisateur.actif:
        raise invalid("mecanicien_id", MESSAGE_MECANICIEN_INVALIDE)
    return utilisateur


def lister_mecaniciens(db: Session) -> list[Utilisateur]:
    return list(
        db.scalars(
            select(Utilisateur)
            .where(Utilisateur.role == Role.MECANICIEN, Utilisateur.actif.is_(True))
            .order_by(Utilisateur.nom, Utilisateur.id)
        )
    )


def appliquer_kilometrage_entree(vehicule: Vehicule, kilometrage_entree: int | None) -> None:
    """Le compteur ne recule pas : inférieur → 422 ; supérieur → la fiche est mise à jour."""
    if kilometrage_entree is None:
        return
    if kilometrage_entree < vehicule.kilometrage:
        raise invalid("kilometrage_entree", message_kilometrage_inferieur(vehicule.kilometrage))
    if kilometrage_entree > vehicule.kilometrage:
        vehicule.kilometrage = kilometrage_entree


def verifier_modifiable(ordre: OrdreTravail) -> None:
    if ordre.statut == StatutOT.LIVRE:
        raise conflict("ordre_livre", MESSAGE_ORDRE_LIVRE)


def creer_ordre(
    db: Session, entree: OrdreEntree, auteur: Utilisateur, maintenant: datetime, annee: int
) -> OrdreTravail:
    """Ouvre un OT. Toutes les vérifications passent AVANT la réservation du numéro.

    Verrous, toujours dans cet ordre : véhicule (si un kilométrage est relevé), puis compteur."""
    vehicule = vehicule_de_l_ordre(
        db, entree.vehicule_id, verrouiller=entree.kilometrage_entree is not None
    )
    mecanicien = mecanicien_actif(db, entree.mecanicien_id)
    appliquer_kilometrage_entree(vehicule, entree.kilometrage_entree)

    ordre = OrdreTravail(
        numero=prochain_numero(db, TYPE_ORDRE_TRAVAIL, annee),
        vehicule=vehicule,
        mecanicien=mecanicien,
        demande_client=entree.demande_client,
        diagnostic=entree.diagnostic,
        statut=StatutOT.A_FAIRE,
        prioritaire=entree.prioritaire,
        kilometrage_entree=entree.kilometrage_entree,
        restitution_prevue=entree.restitution_prevue,
        ouvert_le=maintenant,
        createur=auteur,
    )
    ordre.taches = [
        TacheOT(libelle=t.libelle, duree_prevue_minutes=t.duree_prevue_minutes, position=i)
        for i, t in enumerate(entree.taches)
    ]
    tracer(ordre, None, StatutOT.A_FAIRE, auteur, maintenant)
    db.add(ordre)
    db.flush()
    return ordre


def _remplacer_taches(ordre: OrdreTravail, taches: Sequence[TacheModification]) -> None:
    existantes = {t.id: t for t in ordre.taches}
    vues: set[int] = set()
    nouvelles: list[TacheOT] = []
    for i, donnees in enumerate(taches):
        if donnees.id is None:
            if ordre.statut == StatutOT.TERMINE:
                raise conflict("ordre_pret", MESSAGE_ORDRE_PRET)
            tache = TacheOT(
                libelle=donnees.libelle, duree_prevue_minutes=donnees.duree_prevue_minutes
            )
        else:
            trouvee = existantes.get(donnees.id)
            if trouvee is None or donnees.id in vues:
                raise invalid(f"taches.{i}.id", MESSAGE_TACHE_INTROUVABLE)
            vues.add(donnees.id)
            tache = trouvee
            tache.libelle = donnees.libelle
            tache.duree_prevue_minutes = donnees.duree_prevue_minutes
        tache.position = i
        nouvelles.append(tache)
    # Les tâches absentes de la liste sont supprimées (delete-orphan).
    ordre.taches = nouvelles


def modifier_ordre(db: Session, ordre: OrdreTravail, entree: OrdreModification) -> OrdreTravail:
    verifier_modifiable(ordre)
    # Un mécanicien désactivé depuis l'affectation reste affiché tant qu'on ne le change pas.
    if entree.mecanicien_id != ordre.mecanicien_id:
        ordre.mecanicien = mecanicien_actif(db, entree.mecanicien_id)
    ordre.demande_client = entree.demande_client
    ordre.diagnostic = entree.diagnostic
    ordre.prioritaire = entree.prioritaire
    ordre.restitution_prevue = entree.restitution_prevue
    if entree.taches is not None:
        _remplacer_taches(ordre, entree.taches)
    db.flush()
    return ordre


@dataclass(frozen=True)
class FiltresOrdres:
    statuts: Sequence[StatutOT] = ()
    mecanicien_id: int | None = None
    vehicule_id: int | None = None
    # Bornes sur la date d'ouverture, en UTC (jours de Paris convertis par l'appelant).
    ouvert_depuis: datetime | None = None
    ouvert_avant: datetime | None = None
    # Vue « atelier » (kanban) : OT non livrés, plus ceux livrés depuis cet instant.
    livres_depuis: datetime | None = None


@dataclass(frozen=True)
class PageOrdres:
    elements: list[OrdreTravail]
    total: int


def _filtrer(
    requete: Select[tuple[OrdreTravail]], filtres: FiltresOrdres
) -> Select[tuple[OrdreTravail]]:
    if filtres.statuts:
        requete = requete.where(OrdreTravail.statut.in_(filtres.statuts))
    if filtres.mecanicien_id is not None:
        requete = requete.where(OrdreTravail.mecanicien_id == filtres.mecanicien_id)
    if filtres.vehicule_id is not None:
        requete = requete.where(OrdreTravail.vehicule_id == filtres.vehicule_id)
    if filtres.ouvert_depuis is not None:
        requete = requete.where(OrdreTravail.ouvert_le >= filtres.ouvert_depuis)
    if filtres.ouvert_avant is not None:
        requete = requete.where(OrdreTravail.ouvert_le < filtres.ouvert_avant)
    if filtres.livres_depuis is not None:
        requete = requete.where(
            (OrdreTravail.statut != StatutOT.LIVRE)
            | (OrdreTravail.cloture_le >= filtres.livres_depuis)
        )
    return requete


def lister_ordres(db: Session, filtres: FiltresOrdres, page: int, taille: int) -> PageOrdres:
    """OT du plus récemment ouvert au plus ancien."""
    base = _filtrer(select(OrdreTravail), filtres)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    requete = (
        base.options(*CHARGEMENT_ORDRE)
        .order_by(OrdreTravail.ouvert_le.desc(), OrdreTravail.id.desc())
        .offset((page - 1) * taille)
        .limit(taille)
    )
    return PageOrdres(elements=list(db.scalars(requete)), total=total)


def jour_valide(du: date | None, au: date | None) -> None:
    if du is not None and au is not None and au < du:
        raise invalid("au", "La date de fin doit suivre la date de début.")


def historique_vehicule(db: Session, vehicule: Vehicule) -> list[OrdreTravail]:
    """Interventions du véhicule, de la plus récente à la plus ancienne (story S1.4)."""
    return list(
        db.scalars(
            select(OrdreTravail)
            .where(OrdreTravail.vehicule_id == vehicule.id)
            .options(selectinload(OrdreTravail.mecanicien), selectinload(OrdreTravail.taches))
            .order_by(OrdreTravail.ouvert_le.desc(), OrdreTravail.id.desc())
        )
    )
