"""Création et mise à jour des comptes employés (utilisé par la CLI et le jeu de démonstration)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.utilisateur import Role, StatutCompte, Utilisateur
from app.security.hachage import hacher, verifier
from app.services.auth import trouver_par_email
from app.services.courriel import normaliser_courriel

LONGUEUR_MIN_MOT_DE_PASSE = 12


class CompteInvalideError(ValueError):
    """Donnée de compte refusée ; le message est affiché tel quel."""


def separer_nom(nom_complet: str) -> tuple[str, str]:
    """Prénom et nom d'un nom saisi d'un bloc, coupé au premier espace (même règle que la
    migration 0016) : « Nadia Benali » → (« Nadia », « Benali ») ; « Karim B. » → (« Karim »,
    « B. ») ; un seul mot devient le prénom, avec un nom vide."""
    texte = nom_complet.strip()
    prenom, _, nom = texte.partition(" ")
    return prenom, nom.strip()


def valider_email(email: str) -> str:
    try:
        return normaliser_courriel(email)
    except ValueError as exc:
        raise CompteInvalideError(str(exc)) from exc


def valider_mot_de_passe(mot_de_passe: str) -> str:
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise CompteInvalideError(
            f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères."
        )
    return mot_de_passe


def creer_utilisateur(
    db: Session, *, email: str, prenom: str, nom: str, role: Role, mot_de_passe: str
) -> Utilisateur:
    email = valider_email(email)
    prenom, nom = prenom.strip(), nom.strip()
    if not prenom:
        raise CompteInvalideError("Le prénom est obligatoire.")
    if not nom:
        raise CompteInvalideError("Le nom est obligatoire.")
    valider_mot_de_passe(mot_de_passe)
    if trouver_par_email(db, email) is not None:
        raise CompteInvalideError(f"Un compte existe déjà pour {email}.")
    utilisateur = Utilisateur(
        email=email,
        prenom=prenom,
        nom=nom,
        role=role,
        mot_de_passe_hash=hacher(mot_de_passe),
        statut=StatutCompte.ACTIF,
    )
    db.add(utilisateur)
    db.flush()
    return utilisateur


@dataclass(frozen=True)
class CompteDemo:
    email: str
    prenom: str
    nom: str
    role: Role

    @property
    def nom_affiche(self) -> str:
        return " ".join(part for part in (self.prenom, self.nom) if part)


def enregistrer_compte(db: Session, compte: CompteDemo, mot_de_passe: str) -> bool:
    """Crée le compte ou le remet à jour (prénom, nom, rôle, mot de passe, réactivation et
    déblocage).

    Renvoie True si le compte a été créé. Le hash n'est recalculé que si le mot de passe a
    changé : relancer le seed ne modifie rien.
    """
    utilisateur = trouver_par_email(db, compte.email)
    if utilisateur is None:
        db.add(
            Utilisateur(
                email=compte.email,
                prenom=compte.prenom,
                nom=compte.nom,
                role=compte.role,
                mot_de_passe_hash=hacher(mot_de_passe),
                statut=StatutCompte.ACTIF,
            )
        )
        db.flush()
        return True
    utilisateur.prenom = compte.prenom
    utilisateur.nom = compte.nom
    utilisateur.role = compte.role
    utilisateur.statut = StatutCompte.ACTIF
    # Déblocage : un compte de démonstration bloqué pendant une démo redevient utilisable.
    utilisateur.tentatives_echouees = 0
    utilisateur.bloque_jusqu_a = None
    utilisateur.desactive_le = None
    utilisateur.desactive_par = None
    if not verifier(utilisateur.mot_de_passe_hash, mot_de_passe):
        utilisateur.mot_de_passe_hash = hacher(mot_de_passe)
    db.flush()
    return False


def enregistrer_compte_inactif(
    db: Session,
    compte: CompteDemo,
    mot_de_passe: str,
    statut: StatutCompte,
    *,
    maintenant: datetime,
    gerant: Utilisateur | None,
) -> bool:
    """Compte de démonstration hors service (recette du sprint 5), remis dans son état à
    chaque seed : inscription « en_attente » (jamais validée) ou ancien employé « desactive »
    (désactivé par `gerant`, il y a 30 jours à la première création), avec une chronologie
    vraisemblable : arrivée et validation plus d'un an avant la désactivation, dernière
    connexion avant elle (revue du sprint 5 : « Créé le » tombait après les deux).

    Renvoie True si le compte a été créé. Comme `enregistrer_compte`, le hash n'est recalculé
    que si le mot de passe a changé.
    """
    if statut == StatutCompte.ACTIF:
        raise ValueError("Compte actif : utiliser enregistrer_compte.")
    utilisateur = trouver_par_email(db, compte.email)
    cree = utilisateur is None
    if utilisateur is None:
        utilisateur = Utilisateur(
            email=compte.email,
            prenom=compte.prenom,
            nom=compte.nom,
            role=compte.role,
            mot_de_passe_hash=hacher(mot_de_passe),
            statut=statut,
        )
        db.add(utilisateur)
    elif not verifier(utilisateur.mot_de_passe_hash, mot_de_passe):
        utilisateur.mot_de_passe_hash = hacher(mot_de_passe)
    utilisateur.prenom = compte.prenom
    utilisateur.nom = compte.nom
    utilisateur.role = compte.role
    utilisateur.tentatives_echouees = 0
    utilisateur.bloque_jusqu_a = None
    if statut == StatutCompte.EN_ATTENTE:
        utilisateur.valide_le = utilisateur.valide_par = None
        utilisateur.desactive_le = utilisateur.desactive_par = None
    else:
        if utilisateur.statut != StatutCompte.DESACTIVE or utilisateur.desactive_le is None:
            utilisateur.desactive_le = maintenant - timedelta(days=30)
            utilisateur.desactive_par = gerant.id if gerant is not None else None
        _chronologie_ancien_employe(utilisateur, utilisateur.desactive_le, gerant)
    utilisateur.statut = statut
    db.flush()
    return cree


def _chronologie_ancien_employe(
    utilisateur: Utilisateur, desactive_le: datetime, gerant: Utilisateur | None
) -> None:
    """Arrivée (validée par `gerant`) 400 jours avant la désactivation, dernière connexion
    15 jours avant ; une date déjà cohérente n'est pas touchée (seed rejouable)."""
    connexion = utilisateur.derniere_connexion
    if connexion is None or connexion >= desactive_le:
        connexion = utilisateur.derniere_connexion = desactive_le - timedelta(days=15)
    if utilisateur.cree_le is None or utilisateur.cree_le >= connexion:
        utilisateur.cree_le = desactive_le - timedelta(days=400)
    valide = utilisateur.valide_le
    if valide is None or not utilisateur.cree_le <= valide <= connexion:
        utilisateur.valide_le = utilisateur.cree_le
        utilisateur.valide_par = gerant.id if gerant is not None else None
