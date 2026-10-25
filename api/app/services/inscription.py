"""Inscription autonome d'un gérant (story S8.3).

Décision du PO : l'inscription est ouverte, mais tout nouveau compte reste « en attente »
jusqu'à sa validation par un gérant actif (écran « Employés »).

Règles :
- premier compte : quand aucun gérant actif n'existe (installation d'un garage), le compte est
  créé actif avec le rôle gérant et sa session est ouverte (201) ;
- sinon, la demande est enregistrée « en attente » avec le rôle gérant demandé ; le rôle
  définitif est choisi par le gérant qui la valide. La réponse est neutre (202) ;
- e-mail déjà connu : exactement la même réponse 202, rien n'est créé ni modifié (le mot de
  passe du compte existant ne change pas). Le mot de passe saisi est haché dans tous les cas :
  le temps de réponse ne dit pas si l'adresse existe ;
- course : un verrou consultatif de transaction (`pg_advisory_xact_lock`) sérialise les
  inscriptions avant de compter les gérants actifs. Deux premières inscriptions simultanées
  passent l'une après l'autre : la seconde voit le gérant créé par la première et reste en
  attente ;
- abus : au plus `max_comptes_en_attente` demandes en attente (20 par défaut) ; au-delà,
  429 `trop_de_demandes`, contrôlé AVANT l'e-mail pour ne rien révéler sur l'adresse.

Un compte en attente ne se connecte pas. Après un mot de passe correct seulement, la connexion
répond 403 `compte_en_attente` (« Votre compte attend la validation d'un gérant. ») : sans le
mot de passe, on reçoit le même « Identifiants invalides. » que pour une adresse inconnue.
"""

import logging
from datetime import datetime

from fastapi import status
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.schemas.utilisateur import InscriptionEntree
from app.security.hachage import hacher

journal = logging.getLogger("etabli.inscription")

# Clé du verrou consultatif des inscriptions (« ETAB » en hexadécimal ASCII).
VERROU_INSCRIPTION = 0x45544142

MESSAGE_DEMANDE_ENREGISTREE = (
    "Demande enregistrée. Un gérant du garage doit valider votre compte avant votre première"
    " connexion."
)
MESSAGE_PREMIER_COMPTE = "Compte créé. Vous êtes le gérant du garage."
MESSAGE_TROP_DE_DEMANDES = (
    "Trop de demandes attendent déjà leur validation. Contactez le gérant du garage."
)


def trop_de_demandes() -> AppError:
    return AppError(status.HTTP_429_TOO_MANY_REQUESTS, "trop_de_demandes", MESSAGE_TROP_DE_DEMANDES)


def gerant_actif_existe(db: Session) -> bool:
    return bool(
        db.scalar(
            select(
                exists().where(
                    Utilisateur.role == Role.GERANT, Utilisateur.statut == StatutCompte.ACTIF
                )
            )
        )
    )


def compter_en_attente(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(Utilisateur.id)).where(Utilisateur.statut == StatutCompte.EN_ATTENTE)
        )
        or 0
    )


def inscrire(
    db: Session, entree: InscriptionEntree, maintenant: datetime, settings: Settings
) -> Utilisateur | None:
    """Enregistre l'inscription. Renvoie le compte actif créé s'il s'agit du premier compte du
    garage (session à ouvrir), None sinon (demande en attente, ou e-mail déjà connu)."""
    mot_de_passe_hash = hacher(entree.mot_de_passe)
    db.execute(select(func.pg_advisory_xact_lock(VERROU_INSCRIPTION)))
    premier = not gerant_actif_existe(db)
    if not premier and compter_en_attente(db) >= settings.max_comptes_en_attente:
        journal.info("Inscription refusée : trop de demandes en attente.")
        raise trop_de_demandes()
    if db.scalar(select(Utilisateur.id).where(Utilisateur.email == entree.email)) is not None:
        journal.info("Inscription : e-mail déjà connu, aucune modification.")
        return None
    utilisateur = Utilisateur(
        prenom=entree.prenom,
        nom=entree.nom,
        email=entree.email,
        role=Role.GERANT,
        mot_de_passe_hash=mot_de_passe_hash,
        statut=StatutCompte.ACTIF if premier else StatutCompte.EN_ATTENTE,
        valide_le=maintenant if premier else None,
        derniere_connexion=maintenant if premier else None,
    )
    try:
        with db.begin_nested():
            db.add(utilisateur)
            db.flush()
    except IntegrityError as exc:
        # Même e-mail créé entre-temps par le gérant (POST /utilisateurs) : réponse neutre.
        if "uq_utilisateur_email" not in str(exc.orig):
            raise
        journal.info("Inscription : e-mail pris entre-temps, aucune modification.")
        return None
    if premier:
        journal.info("Premier compte du garage créé : gérant %s.", utilisateur.id)
        return utilisateur
    journal.info("Demande d'inscription %s en attente de validation.", utilisateur.id)
    return None
