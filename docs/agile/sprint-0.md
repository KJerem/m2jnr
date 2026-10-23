# Sprint 0 — Initiation

**Dates** : 26 au 30 octobre 2026 · **Points** : 0 (sprint technique) · **Tag** : `sprint-0`

## Objectif
Un projet prêt à développer : chaque membre lance l'application et les tests avec une seule commande.

## Tâches réalisées
| # | Tâche | Type | Réalisation |
| --- | --- | --- | --- |
| 0.1 | Dépôt Git, `main` et `develop`, `.gitignore` | INIT | + `.gitattributes` (fins de ligne LF), `.editorconfig` |
| 0.2 | Environnement et dépendances | INIT | `requirements*.txt` et `package.json` épinglés |
| 0.3 | Architecture en dossiers | INIT | `api/app/{models,schemas,routers,services,security}`, `web/src/{app,components,lib,styles}` |
| 0.4 | `.env` et `.env.example` | INIT | secrets générés localement, jamais versionnés |
| 0.5 | Base de données et `init_db` | BDD | PostgreSQL 16 en Docker, Alembic, `python -m app.cli init-db` |
| 0.6 | Modèle UML des tables | BDD | `docs/uml/modele-donnees.md` (Mermaid) |
| 0.7 | Gabarit de page de base | FRONT | menu par rôle, thème clair/sombre, 403/404, composants du design system |
| 0.8 | Tests « l'application démarre » | TEST | pytest (3 tests), Vitest (11 tests), CI |
| 0.9 | Tableau et Definition of Done | INIT | `docs/agile/` |

## Adaptations par rapport au plan initial
Le plan prévoyait Flask, SQLite et des templates serveur. L'équipe a retenu Docker, PostgreSQL,
FastAPI et Next.js : chaque tâche garde son intention, traduite dans cette stack (voir le README).

## Démo
`docker compose up -d --build`, puis http://localhost:3000 (gabarit) et http://localhost:8000/docs.

## Rétrospective
- **Bien** : environnement identique pour tous grâce à Docker ; base de test isolée.
- **À améliorer** : `npm ci` refusait un lockfile produit sous Windows (conflit de dépendances
  optionnelles). Action : toujours valider le lockfile dans le conteneur avant de pousser.
