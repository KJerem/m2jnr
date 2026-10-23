"""Commandes d'administration : python -m app.cli <commande>.

- init-db : applique toutes les migrations Alembic (équivalent du init_db du backlog)
"""

import argparse
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Administration d'Établi")
    sub = parser.add_subparsers(dest="commande", required=True)
    sub.add_parser("init-db", help="Créer ou mettre à jour le schéma de la base")

    args = parser.parse_args(argv)
    if args.commande == "init-db":
        init_db()
    return 0


if __name__ == "__main__":
    sys.exit(main())
