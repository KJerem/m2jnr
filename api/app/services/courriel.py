"""Validation des adresses e-mail (comptes employés et fiches clients)."""

from email_validator import EmailNotValidError, validate_email

MESSAGE_EMAIL_INVALIDE = "Adresse e-mail invalide."


def normaliser_courriel(valeur: str) -> str:
    """Adresse validée et mise en minuscules ; ValueError en français si elle est invalide.

    Le domaine réservé `.test` est accepté : les données de démonstration l'utilisent pour
    rester fictives. Aucune vérification DNS n'est faite (pas de requête réseau).
    """
    try:
        resultat = validate_email(valeur.strip(), check_deliverability=False, test_environment=True)
    except EmailNotValidError as exc:
        raise ValueError(MESSAGE_EMAIL_INVALIDE) from exc
    return resultat.normalized.lower()
