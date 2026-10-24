"""Commandes d'administration : python -m app.cli <commande>.

- init-db : applique toutes les migrations Alembic (équivalent du init_db du backlog)
- seed : charge le jeu de démonstration (rejouable, sans doublon)
- create-user : crée un compte employé, mot de passe saisi sans écho
"""

import argparse
import getpass
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

API_DIR = Path(__file__).resolve().parent.parent


def init_db() -> None:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    command.upgrade(cfg, "head")
    print("Base de données à jour.")


def seed() -> int:
    from app.config import get_settings
    from app.db import SessionLocal
    from app.services.donnees_demo import SeedImpossibleError, semer

    with SessionLocal() as db:
        try:
            rapport = semer(db, get_settings())
        except SeedImpossibleError as exc:
            print(f"Seed impossible : {exc}", file=sys.stderr)
            return 1
        db.commit()
    for ligne in rapport:
        print(ligne)
    print("Jeu de démonstration chargé.")
    return 0


def create_user(email: str, nom: str, role: str) -> int:
    from app.db import SessionLocal
    from app.models.utilisateur import Role
    from app.services.utilisateurs import (
        CompteInvalideError,
        creer_utilisateur,
        valider_mot_de_passe,
    )

    try:
        mot_de_passe = valider_mot_de_passe(getpass.getpass("Mot de passe (12 caractères min.) : "))
        if getpass.getpass("Confirmer le mot de passe : ") != mot_de_passe:
            raise CompteInvalideError("Les deux mots de passe ne correspondent pas.")
        with SessionLocal() as db:
            utilisateur = creer_utilisateur(
                db, email=email, nom=nom, role=Role(role), mot_de_passe=mot_de_passe
            )
            db.commit()
            print(f"Compte créé : {utilisateur.nom} ({utilisateur.email}), rôle {role}.")
    except CompteInvalideError as exc:
        print(f"Création impossible : {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Administration d'Établi"
    )
    sub = parser.add_subparsers(dest="commande", required=True)
    sub.add_parser("init-db", help="Créer ou mettre à jour le schéma de la base")
    sub.add_parser("seed", help="Charger le jeu de démonstration (comptes, clients, véhicules)")
    creer = sub.add_parser("create-user", help="Créer un compte employé")
    creer.add_argument("--email", required=True)
    creer.add_argument("--nom", required=True)
    creer.add_argument("--role", required=True, choices=["gerant", "mecanicien"])

    args = parser.parse_args(argv)
    if args.commande == "init-db":
        init_db()
    elif args.commande == "seed":
        return seed()
    elif args.commande == "create-user":
        return create_user(args.email, args.nom, args.role)
    return 0


if __name__ == "__main__":
    sys.exit(main())
