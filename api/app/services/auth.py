"""Connexion des employés : vérification du mot de passe et blocage après échecs répétés.

Règles (story S8.1) :
- e-mail inconnu, mauvais mot de passe ou compte désactivé : 401 « Identifiants invalides. »,
  sans dire ce qui est faux ; un compte désactivé est traité comme un e-mail inconnu (aucun
  compteur, jamais de blocage) ;
- compte en attente de validation (story S8.3) : même 401 avec un mauvais mot de passe (ni
  compteur ni blocage) ; avec le bon, 403 `compte_en_attente`, qui n'apprend rien à qui ne
  connaît pas déjà le mot de passe ;
- chaque échec incrémente `tentatives_echouees` ; au 5ᵉ échec consécutif, le compte est bloqué
  15 minutes (réglages `max_login_attempts` et `lockout_minutes`) ;
- pendant le blocage, toute tentative est refusée (423), même avec le bon mot de passe, et le
  blocage n'est pas prolongé ; à son expiration, le compteur repart de zéro ;
- une connexion réussie remet le compteur à zéro et enregistre `derniere_connexion`.

Le journal ne contient jamais de mot de passe ni d'e-mail saisi, seulement l'id du compte.
"""

import logging
from datetime import datetime, timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models.utilisateur import StatutCompte, Utilisateur
from app.security.hachage import doit_rehacher, hacher, hash_factice, verifier
from app.services.format import formater_heure

journal = logging.getLogger("etabli.auth")

MESSAGE_IDENTIFIANTS_INVALIDES = "Identifiants invalides."


def identifiants_invalides() -> AppError:
    return AppError(
        status.HTTP_401_UNAUTHORIZED, "identifiants_invalides", MESSAGE_IDENTIFIANTS_INVALIDES
    )


MESSAGE_COMPTE_EN_ATTENTE = "Votre compte attend la validation d'un gérant."


def compte_en_attente() -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "compte_en_attente", MESSAGE_COMPTE_EN_ATTENTE)


def message_blocage(jusqu_a: datetime, settings: Settings) -> str:
    heure = formater_heure(jusqu_a, settings.timezone)
    return f"Compte bloqué jusqu'à {heure} après {settings.max_login_attempts} essais erronés."


def compte_bloque(jusqu_a: datetime, settings: Settings) -> AppError:
    return AppError(
        status.HTTP_423_LOCKED,
        "compte_bloque",
        message_blocage(jusqu_a, settings),
        details={"bloque_jusqu_a": jusqu_a.isoformat()},
    )


def normaliser_email(email: str) -> str:
    return email.strip().lower()


def trouver_par_email(db: Session, email: str, *, verrouiller: bool = False) -> Utilisateur | None:
    adresse = normaliser_email(email)
    if "\x00" in adresse:
        # PostgreSQL refuse NUL dans un texte (erreur 500) : aucun compte n'a cette adresse.
        return None
    requete = select(Utilisateur).where(Utilisateur.email == adresse)
    if verrouiller:
        requete = requete.with_for_update()
    return db.scalars(requete).one_or_none()


def connecter(
    db: Session, email: str, mot_de_passe: str, maintenant: datetime, settings: Settings
) -> Utilisateur:
    """Authentifie un employé ou lève une AppError (401 ou 423).

    Les échecs sont validés en base avant de lever l'erreur : sinon l'annulation de la
    transaction de la requête effacerait le compteur et le blocage ne se déclencherait jamais.
    La ligne est verrouillée (SELECT … FOR UPDATE) pour que deux tentatives simultanées
    comptent bien pour deux.
    """
    utilisateur = trouver_par_email(db, email, verrouiller=True)
    if utilisateur is None:
        verifier(hash_factice(), mot_de_passe)
        journal.info("Connexion refusée : e-mail inconnu.")
        raise identifiants_invalides()

    if utilisateur.statut == StatutCompte.EN_ATTENTE:
        # Inscription pas encore validée (story S8.3) : sans le bon mot de passe, la réponse
        # d'un e-mail inconnu (ni compteur ni blocage) ; avec, un message qui ne révèle rien
        # à qui ne connaît pas déjà le mot de passe.
        if not verifier(utilisateur.mot_de_passe_hash, mot_de_passe):
            journal.info("Connexion refusée : compte %s en attente.", utilisateur.id)
            raise identifiants_invalides()
        journal.info("Connexion refusée : compte %s en attente de validation.", utilisateur.id)
        raise compte_en_attente()

    if not utilisateur.actif:
        # Traité comme un e-mail inconnu : ni compteur ni blocage (un 423 révélerait que
        # l'adresse existe), et un temps de réponse comparable grâce au hash factice.
        verifier(hash_factice(), mot_de_passe)
        journal.info("Connexion refusée : compte %s désactivé.", utilisateur.id)
        raise identifiants_invalides()

    if utilisateur.bloque_jusqu_a is not None:
        if maintenant < utilisateur.bloque_jusqu_a:
            journal.info("Connexion refusée : compte %s bloqué.", utilisateur.id)
            raise compte_bloque(utilisateur.bloque_jusqu_a, settings)
        # Blocage expiré : le compteur repart de zéro.
        utilisateur.bloque_jusqu_a = None
        utilisateur.tentatives_echouees = 0

    if not verifier(utilisateur.mot_de_passe_hash, mot_de_passe):
        utilisateur.tentatives_echouees += 1
        fin_blocage: datetime | None = None
        if utilisateur.tentatives_echouees >= settings.max_login_attempts:
            fin_blocage = maintenant + timedelta(minutes=settings.lockout_minutes)
            utilisateur.bloque_jusqu_a = fin_blocage
        db.commit()
        journal.info(
            "Connexion refusée : mauvais mot de passe pour le compte %s (%s échec(s)).",
            utilisateur.id,
            utilisateur.tentatives_echouees,
        )
        if fin_blocage is not None:
            raise compte_bloque(fin_blocage, settings)
        raise identifiants_invalides()

    utilisateur.tentatives_echouees = 0
    utilisateur.bloque_jusqu_a = None
    utilisateur.derniere_connexion = maintenant
    if doit_rehacher(utilisateur.mot_de_passe_hash):
        utilisateur.mot_de_passe_hash = hacher(mot_de_passe)
    db.flush()
    journal.info("Connexion réussie du compte %s.", utilisateur.id)
    return utilisateur
