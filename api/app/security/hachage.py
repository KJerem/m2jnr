"""Hachage des mots de passe en argon2id (paramètres par défaut d'argon2-cffi, RFC 9106)."""

from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hacheur = PasswordHasher()


def hacher(mot_de_passe: str) -> str:
    return _hacheur.hash(mot_de_passe)


def verifier(hash_enregistre: str, mot_de_passe: str) -> bool:
    """Vrai si le mot de passe correspond ; faux s'il est faux ou si le hash est illisible."""
    try:
        return _hacheur.verify(hash_enregistre, mot_de_passe)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def doit_rehacher(hash_enregistre: str) -> bool:
    """Vrai si le hash a été produit avec des paramètres plus faibles que les actuels."""
    return _hacheur.check_needs_rehash(hash_enregistre)


@lru_cache
def hash_factice() -> str:
    """Hash d'un mot de passe jetable, vérifié pour un e-mail inconnu.

    La réponse prend alors le même temps que pour un compte existant : on ne peut pas deviner
    quels e-mails sont enregistrés en mesurant la durée de la connexion.
    """
    return hacher("compte-inexistant-verification-a-temps-constant")
