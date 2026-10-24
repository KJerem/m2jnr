"""Statut du devis (story S4.2) : brouillon → envoyé → accepté ou refusé.

Règles :
- brouillon → envoye (le devis est remis au client : aucun e-mail n'est envoyé par
  l'application, l'envoi se fait de vive voix, sur papier ou par la messagerie du garage) ;
- envoye → accepte ou envoye → refuse (réponse du client) ;
- tout autre passage, et le maintien dans le même statut, sont refusés (409
  `transition_devis_interdite`) ; une décision (acceptée ou refusée) est définitive ;
- seul un brouillon se modifie (409 `devis_verrouille` sinon), seul un devis accepté se
  facture (409 `devis_non_accepte`), un devis refusé se remplace par un nouveau devis ;
- dates d'envoi et de décision lues sur l'horloge injectée ; l'auteur de la décision est
  enregistré. L'appelant verrouille le devis (SELECT … FOR UPDATE).
"""

from datetime import datetime

from app.errors import AppError, conflict
from app.models.devis import Devis, StatutDevis
from app.models.utilisateur import Utilisateur

LIBELLES_STATUT_DEVIS: dict[StatutDevis, str] = {
    StatutDevis.BROUILLON: "Brouillon",
    StatutDevis.ENVOYE: "Envoyé",
    StatutDevis.ACCEPTE: "Accepté",
    StatutDevis.REFUSE: "Refusé",
}

TRANSITIONS_DEVIS: dict[StatutDevis, frozenset[StatutDevis]] = {
    StatutDevis.BROUILLON: frozenset({StatutDevis.ENVOYE}),
    StatutDevis.ENVOYE: frozenset({StatutDevis.ACCEPTE, StatutDevis.REFUSE}),
    StatutDevis.ACCEPTE: frozenset(),
    StatutDevis.REFUSE: frozenset(),
}

MESSAGE_DEVIS_VERROUILLE = (
    "Ce devis a été envoyé : il ne se modifie plus. "
    "Refusé, il peut être remplacé par un nouveau devis."
)
MESSAGE_DEVIS_NON_ACCEPTE = "Seul un devis accepté peut être facturé."


def transition_devis_interdite(message: str, ancien: StatutDevis) -> AppError:
    return conflict("transition_devis_interdite", message, statut=ancien.value)


def verifier_transition_devis(ancien: StatutDevis, nouveau: StatutDevis) -> None:
    """Fonction pure : laisse passer brouillon → envoyé et envoyé → accepté ou refusé."""
    if nouveau in TRANSITIONS_DEVIS[ancien]:
        return
    de, vers = LIBELLES_STATUT_DEVIS[ancien], LIBELLES_STATUT_DEVIS[nouveau]
    if nouveau == ancien:
        raise transition_devis_interdite(f"Le devis est déjà « {de} ».", ancien)
    if ancien in (StatutDevis.ACCEPTE, StatutDevis.REFUSE):
        raise transition_devis_interdite(
            f"Le devis est « {de} » : la décision du client est définitive.", ancien
        )
    if ancien == StatutDevis.BROUILLON:
        raise transition_devis_interdite(
            f"Passage de « {de} » à « {vers} » impossible : "
            "le devis doit d'abord être envoyé au client.",
            ancien,
        )
    raise transition_devis_interdite(
        f"Passage de « {de} » à « {vers} » impossible : pas de retour en arrière.", ancien
    )


def changer_statut_devis(
    devis: Devis, nouveau: StatutDevis, auteur: Utilisateur, maintenant: datetime
) -> Devis:
    """Applique la transition (devis verrouillé par l'appelant) et la date."""
    verifier_transition_devis(devis.statut, nouveau)
    if nouveau == StatutDevis.ENVOYE:
        devis.envoye_le = maintenant
    else:
        devis.decide_le = maintenant
        devis.decideur = auteur
    devis.statut = nouveau
    return devis


def verifier_brouillon(devis: Devis) -> None:
    """409 `devis_verrouille` si le devis n'est plus un brouillon."""
    if devis.statut != StatutDevis.BROUILLON:
        raise conflict("devis_verrouille", MESSAGE_DEVIS_VERROUILLE, statut=devis.statut.value)


def verifier_accepte(devis: Devis) -> None:
    """409 `devis_non_accepte` si le devis n'est pas accepté."""
    if devis.statut != StatutDevis.ACCEPTE:
        raise conflict("devis_non_accepte", MESSAGE_DEVIS_NON_ACCEPTE, statut=devis.statut.value)
