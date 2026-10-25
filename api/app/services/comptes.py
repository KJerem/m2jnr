"""Gestion des comptes des employés par le gérant (story S8.2).

Règles :
- e-mail unique sans tenir compte de la casse (citext) : 409 `email_existant`, y compris pour
  deux créations simultanées (contrainte unique de la base) ;
- mot de passe de 12 caractères au moins, haché en argon2id, jamais renvoyé ;
- un compte créé par le gérant est actif tout de suite (le gérant le valide en le créant) ;
- le gérant ne change pas son propre rôle et ne se désactive pas (409 `soi_meme`) ;
- il reste toujours au moins un gérant actif (409 `dernier_gerant`). Les lignes des gérants
  actifs sont verrouillées (SELECT … FOR UPDATE, par id croissant) avant de les compter : deux
  gérants qui se rétrogradent ou se désactivent l'un l'autre en même temps passent l'un après
  l'autre, et le second voit qu'il ne resterait personne ;
- désactiver : actif → desactive (date et auteur gardés) ; réactiver : desactive → actif ;
  un compte en attente se valide (rôle choisi par le gérant) ou se refuse, ce qui supprime
  la demande (story S8.3) ;
- réinitialiser le mot de passe débloque aussi le compte ; débloquer remet le compteur
  d'échecs à zéro.

Un compte désactivé ne se connecte plus (même réponse qu'un e-mail inconnu) et sa session
ouverte est refusée à la requête suivante : `get_current_user` relit le compte à chaque
requête et n'accepte que le statut « actif ». La désactivation et la réinitialisation du
mot de passe datent aussi `sessions_valides_depuis` : les sessions ouvertes avant restent
refusées après une réactivation, et un mot de passe réinitialisé coupe les sessions de
l'ancien (revue du sprint 5).
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from fastapi import status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import id_possible
from app.errors import AppError, conflict, not_found
from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.schemas.utilisateur import UtilisateurEntree, UtilisateurModification
from app.security.hachage import hacher
from app.services.recherche import chaque_mot_dans

MESSAGE_INTROUVABLE = "Employé introuvable."
MESSAGE_EMAIL_EXISTANT = "Un compte existe déjà avec cet e-mail."
MESSAGE_DERNIER_GERANT = "Il doit rester au moins un gérant actif."
MESSAGE_SOI_MEME_ROLE = "Vous ne pouvez pas changer votre propre rôle."
MESSAGE_SOI_MEME_DESACTIVER = "Vous ne pouvez pas désactiver votre propre compte."
MESSAGE_DEJA_ACTIF = "Ce compte est déjà actif."
MESSAGE_DEJA_DESACTIVE = "Ce compte est déjà désactivé."
MESSAGE_EN_ATTENTE = "Ce compte attend sa validation : validez-le ou refusez la demande."
MESSAGE_PAS_EN_ATTENTE = "Ce compte n'attend pas de validation."

# Comptes en attente d'abord (à traiter), puis actifs, puis désactivés.
ORDRE_STATUT = case(
    (Utilisateur.statut == StatutCompte.EN_ATTENTE, 0),
    (Utilisateur.statut == StatutCompte.ACTIF, 1),
    else_=2,
)


@dataclass(frozen=True)
class PageUtilisateurs:
    elements: list[Utilisateur]
    total: int


# --- Règles pures ---------------------------------------------------------------------------


def reste_un_gerant_actif(cible_id: int, gerants_actifs: Collection[int]) -> bool:
    """Vrai si un gérant actif autre que `cible_id` existe."""
    return any(identifiant != cible_id for identifiant in gerants_actifs)


def refus_retrait(
    cible: Utilisateur, gerants_actifs: Collection[int], *, retire_le_gerant: bool
) -> AppError | None:
    """409 `dernier_gerant` si l'opération retire le dernier gérant actif."""
    est_gerant_actif = cible.role == Role.GERANT and cible.statut == StatutCompte.ACTIF
    if (
        retire_le_gerant
        and est_gerant_actif
        and not reste_un_gerant_actif(cible.id, gerants_actifs)
    ):
        return conflict("dernier_gerant", MESSAGE_DERNIER_GERANT)
    return None


def email_existant() -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "email_existant",
        MESSAGE_EMAIL_EXISTANT,
        champs={"email": MESSAGE_EMAIL_EXISTANT},
    )


# --- Lecture --------------------------------------------------------------------------------


def obtenir_utilisateur(
    db: Session, utilisateur_id: int, *, verrouiller: bool = False
) -> Utilisateur:
    utilisateur = None
    if id_possible(utilisateur_id):
        requete = select(Utilisateur).where(Utilisateur.id == utilisateur_id)
        if verrouiller:
            requete = requete.with_for_update().execution_options(populate_existing=True)
        utilisateur = db.scalars(requete).one_or_none()
    if utilisateur is None:
        raise not_found(MESSAGE_INTROUVABLE)
    return utilisateur


def lister_utilisateurs(
    db: Session,
    page: int,
    taille: int,
    *,
    mots: tuple[str, ...] | None = None,
    role: Role | None = None,
    statut: StatutCompte | None = None,
) -> PageUtilisateurs:
    """Comptes filtrés (recherche sur prénom, nom et e-mail, rôle, statut) ; en attente
    d'abord, puis actifs, puis désactivés, et par nom."""
    base = select(Utilisateur)
    if mots:
        texte = func.concat_ws(" ", Utilisateur.prenom, Utilisateur.nom, Utilisateur.email)
        base = base.where(chaque_mot_dans(texte, mots))
    if role is not None:
        base = base.where(Utilisateur.role == role)
    if statut is not None:
        base = base.where(Utilisateur.statut == statut)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    elements = list(
        db.scalars(
            base.order_by(
                ORDRE_STATUT,
                func.lower(Utilisateur.nom),
                func.lower(Utilisateur.prenom),
                Utilisateur.id,
            )
            .offset((page - 1) * taille)
            .limit(taille)
        )
    )
    return PageUtilisateurs(elements=elements, total=total)


def verrouiller_gerants_actifs(db: Session) -> list[int]:
    """Identifiants des gérants actifs, lignes verrouillées jusqu'à la fin de la transaction
    (par id croissant : deux requêtes prennent les verrous dans le même ordre)."""
    return list(
        db.scalars(
            select(Utilisateur.id)
            .where(Utilisateur.role == Role.GERANT, Utilisateur.statut == StatutCompte.ACTIF)
            .order_by(Utilisateur.id)
            .with_for_update()
        )
    )


# --- Écriture -------------------------------------------------------------------------------


def _verifier_email_libre(db: Session, email: str, *, sauf_id: int | None = None) -> None:
    requete = select(Utilisateur.id).where(Utilisateur.email == email)
    if sauf_id is not None:
        requete = requete.where(Utilisateur.id != sauf_id)
    if db.scalar(requete) is not None:
        raise email_existant()


def _enregistrer(db: Session, utilisateur: Utilisateur) -> Utilisateur:
    """Écrit en base ; un e-mail pris entre-temps (requête simultanée) donne aussi un 409."""
    try:
        with db.begin_nested():
            db.add(utilisateur)
            db.flush()
    except IntegrityError as exc:
        if "uq_utilisateur_email" not in str(exc.orig):
            raise
        raise email_existant() from exc
    db.refresh(utilisateur)
    return utilisateur


def creer_compte(
    db: Session, entree: UtilisateurEntree, acteur: Utilisateur, maintenant: datetime
) -> Utilisateur:
    _verifier_email_libre(db, entree.email)
    utilisateur = Utilisateur(
        prenom=entree.prenom,
        nom=entree.nom,
        email=entree.email,
        role=entree.role,
        mot_de_passe_hash=hacher(entree.mot_de_passe),
        statut=StatutCompte.ACTIF,
        valide_le=maintenant,
        valide_par=acteur.id,
    )
    return _enregistrer(db, utilisateur)


def modifier_compte(
    db: Session, utilisateur_id: int, entree: UtilisateurModification, acteur: Utilisateur
) -> Utilisateur:
    gerants = verrouiller_gerants_actifs(db)
    cible = obtenir_utilisateur(db, utilisateur_id, verrouiller=True)
    if entree.role != cible.role:
        if cible.id == acteur.id:
            raise conflict("soi_meme", MESSAGE_SOI_MEME_ROLE)
        refus = refus_retrait(cible, gerants, retire_le_gerant=entree.role != Role.GERANT)
        if refus is not None:
            raise refus
    _verifier_email_libre(db, entree.email, sauf_id=cible.id)
    cible.prenom = entree.prenom
    cible.nom = entree.nom
    cible.email = entree.email
    cible.role = entree.role
    return _enregistrer(db, cible)


def reinitialiser_mot_de_passe(
    db: Session, utilisateur_id: int, mot_de_passe: str, maintenant: datetime
) -> Utilisateur:
    """Nouveau mot de passe choisi par le gérant ; le compte est aussi débloqué et ses
    sessions ouvertes sont coupées (une session volée ne survit pas à la réinitialisation)."""
    cible = obtenir_utilisateur(db, utilisateur_id, verrouiller=True)
    cible.mot_de_passe_hash = hacher(mot_de_passe)
    cible.sessions_valides_depuis = maintenant
    cible.tentatives_echouees = 0
    cible.bloque_jusqu_a = None
    db.flush()
    return cible


def debloquer(db: Session, utilisateur_id: int) -> Utilisateur:
    cible = obtenir_utilisateur(db, utilisateur_id, verrouiller=True)
    cible.tentatives_echouees = 0
    cible.bloque_jusqu_a = None
    db.flush()
    return cible


def desactiver(
    db: Session, utilisateur_id: int, acteur: Utilisateur, maintenant: datetime
) -> Utilisateur:
    gerants = verrouiller_gerants_actifs(db)
    cible = obtenir_utilisateur(db, utilisateur_id, verrouiller=True)
    if cible.id == acteur.id:
        raise conflict("soi_meme", MESSAGE_SOI_MEME_DESACTIVER)
    if cible.statut == StatutCompte.DESACTIVE:
        raise conflict("statut_incompatible", MESSAGE_DEJA_DESACTIVE)
    if cible.statut == StatutCompte.EN_ATTENTE:
        raise conflict("statut_incompatible", MESSAGE_EN_ATTENTE)
    refus = refus_retrait(cible, gerants, retire_le_gerant=True)
    if refus is not None:
        raise refus
    cible.statut = StatutCompte.DESACTIVE
    cible.desactive_le = maintenant
    cible.desactive_par = acteur.id
    cible.sessions_valides_depuis = maintenant
    db.flush()
    return cible


def reactiver(db: Session, utilisateur_id: int) -> Utilisateur:
    cible = obtenir_utilisateur(db, utilisateur_id, verrouiller=True)
    if cible.statut == StatutCompte.ACTIF:
        raise conflict("statut_incompatible", MESSAGE_DEJA_ACTIF)
    if cible.statut == StatutCompte.EN_ATTENTE:
        raise conflict("statut_incompatible", MESSAGE_EN_ATTENTE)
    cible.statut = StatutCompte.ACTIF
    db.flush()
    return cible


# --- Inscriptions en attente (story S8.3) ---------------------------------------------------


def _en_attente(db: Session, utilisateur_id: int) -> Utilisateur:
    cible = obtenir_utilisateur(db, utilisateur_id, verrouiller=True)
    if cible.statut != StatutCompte.EN_ATTENTE:
        raise conflict("statut_incompatible", MESSAGE_PAS_EN_ATTENTE)
    return cible


def valider(
    db: Session, utilisateur_id: int, role: Role, acteur: Utilisateur, maintenant: datetime
) -> Utilisateur:
    """Le gérant valide une inscription en choisissant le rôle définitif du compte."""
    cible = _en_attente(db, utilisateur_id)
    cible.statut = StatutCompte.ACTIF
    cible.role = role
    cible.valide_le = maintenant
    cible.valide_par = acteur.id
    db.flush()
    return cible


def refuser(db: Session, utilisateur_id: int) -> None:
    """Refus d'une inscription : la demande est supprimée (rien n'est gardé d'une personne qui
    n'a jamais travaillé au garage) ; l'e-mail peut servir à une nouvelle demande."""
    db.delete(_en_attente(db, utilisateur_id))
    db.flush()
