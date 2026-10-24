"""Statuts de l'ordre de travail : transitions autorisées, historique, tâches terminées.

Règles (story S3.2) :
- a_faire → en_cours → termine → livre, une étape à la fois, sans retour en arrière ;
  un saut, un retour ou le même statut sont refusés (409 `transition_interdite`) ;
- « Prêt » (termine) exige que toutes les tâches soient terminées ;
- « Livré » clôt l'OT (`cloture_le`) ; plus rien n'y est modifiable ;
- chaque changement est tracé dans `historique_statut` avec l'heure (horloge injectée) et
  son auteur. Le gérant et le mécanicien peuvent faire avancer n'importe quel OT : un
  collègue peut reprendre un travail, l'historique dit qui a fait quoi.
"""

from datetime import datetime

from app.errors import AppError, conflict, not_found
from app.models.ordre_travail import HistoriqueStatut, OrdreTravail, StatutOT, TacheOT
from app.models.utilisateur import Utilisateur

ORDRE_DES_STATUTS: tuple[StatutOT, ...] = (
    StatutOT.A_FAIRE,
    StatutOT.EN_COURS,
    StatutOT.TERMINE,
    StatutOT.LIVRE,
)

# Libellés des badges du design system (« En attente », « Prêt »…), repris dans les messages.
LIBELLES_STATUT: dict[StatutOT, str] = {
    StatutOT.A_FAIRE: "En attente",
    StatutOT.EN_COURS: "En cours",
    StatutOT.TERMINE: "Prêt",
    StatutOT.LIVRE: "Livré",
}

MESSAGE_TACHES_OUVERTES = "Toutes les tâches doivent être terminées."
MESSAGE_ORDRE_LIVRE = "Un ordre de travail livré ne peut plus être modifié."
MESSAGE_ORDRE_PRET = "Le véhicule est prêt : impossible d'ajouter ou de rouvrir une tâche."
MESSAGE_TACHE_INTROUVABLE = "Tâche introuvable pour cet ordre de travail."


def statut_suivant(statut: StatutOT) -> StatutOT | None:
    """Seul statut autorisé après `statut`, ou None pour un OT livré."""
    rang = ORDRE_DES_STATUTS.index(statut)
    return ORDRE_DES_STATUTS[rang + 1] if rang + 1 < len(ORDRE_DES_STATUTS) else None


def transition_interdite(message: str, ancien: StatutOT) -> AppError:
    return conflict("transition_interdite", message, statut=ancien.value)


def verifier_transition(ancien: StatutOT, nouveau: StatutOT) -> None:
    """Fonction pure : ne laisse passer que l'étape suivante, sinon lève un 409."""
    if nouveau == ancien:
        raise transition_interdite(
            f"L'ordre de travail est déjà « {LIBELLES_STATUT[ancien]} ».", ancien
        )
    if nouveau == statut_suivant(ancien):
        return
    de, vers = LIBELLES_STATUT[ancien], LIBELLES_STATUT[nouveau]
    if ORDRE_DES_STATUTS.index(nouveau) < ORDRE_DES_STATUTS.index(ancien):
        raise transition_interdite(
            f"Passage de « {de} » à « {vers} » impossible : pas de retour en arrière.", ancien
        )
    raise transition_interdite(
        f"Passage de « {de} » à « {vers} » impossible : une étape à la fois.", ancien
    )


def tracer(
    ordre: OrdreTravail,
    ancien: StatutOT | None,
    nouveau: StatutOT,
    auteur: Utilisateur,
    maintenant: datetime,
) -> None:
    ordre.historique.append(
        HistoriqueStatut(ancien=ancien, nouveau=nouveau, change_le=maintenant, utilisateur=auteur)
    )


def changer_statut(
    ordre: OrdreTravail, nouveau: StatutOT, auteur: Utilisateur, maintenant: datetime
) -> OrdreTravail:
    """Fait avancer l'OT d'une étape et trace le changement (l'appelant verrouille l'OT)."""
    ancien = ordre.statut
    verifier_transition(ancien, nouveau)
    if nouveau == StatutOT.TERMINE and any(not t.terminee for t in ordre.taches):
        raise conflict("taches_non_terminees", MESSAGE_TACHES_OUVERTES)
    ordre.statut = nouveau
    if nouveau == StatutOT.LIVRE:
        ordre.cloture_le = maintenant
    tracer(ordre, ancien, nouveau, auteur, maintenant)
    return ordre


def _tache(ordre: OrdreTravail, tache_id: int) -> TacheOT:
    for tache in ordre.taches:
        if tache.id == tache_id:
            return tache
    raise not_found(MESSAGE_TACHE_INTROUVABLE)


def terminer_tache(
    ordre: OrdreTravail, tache_id: int, auteur: Utilisateur, maintenant: datetime
) -> TacheOT:
    """Coche une tâche (sans effet si elle l'est déjà : la première heure de fin est gardée)."""
    if ordre.statut == StatutOT.LIVRE:
        raise conflict("ordre_livre", MESSAGE_ORDRE_LIVRE)
    tache = _tache(ordre, tache_id)
    if not tache.terminee:
        tache.terminee = True
        tache.terminee_le = maintenant
        tache.terminee_par_utilisateur = auteur
    return tache


def rouvrir_tache(ordre: OrdreTravail, tache_id: int) -> TacheOT:
    """Décoche une tâche ; impossible sur un véhicule prêt ou livré (le statut ne recule pas)."""
    if ordre.statut == StatutOT.LIVRE:
        raise conflict("ordre_livre", MESSAGE_ORDRE_LIVRE)
    tache = _tache(ordre, tache_id)
    if ordre.statut == StatutOT.TERMINE and tache.terminee:
        raise conflict("ordre_pret", MESSAGE_ORDRE_PRET)
    tache.terminee = False
    tache.terminee_le = None
    tache.terminee_par_utilisateur = None
    return tache
