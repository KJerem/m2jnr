# Établi — gestion de garage automobile

MVP réalisé en Scrum (sprints de 2 semaines, du 26 octobre au 24 décembre 2026) par une squad de
5 personnes. Il remplace le papier et le tableur des garagistes indépendants : clients, véhicules,
rendez-vous, ordres de travail, devis, factures.

| Couche | Technologie |
| --- | --- |
| Base de données | PostgreSQL 16 (Docker), migrations Alembic |
| API | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 |
| Interface | Next.js 16 (App Router, TypeScript), design system Établi |
| Tests | pytest (base dédiée), Vitest + Testing Library, Playwright |

## Démarrer

Prérequis : Docker Desktop (ou Docker Engine + Compose v2).

```bash
cp .env.example .env          # puis remplacer chaque valeur « a-changer »
docker compose up -d --build  # base, base de test, API, interface
```

- Interface : http://localhost:3000
- API et documentation OpenAPI : http://localhost:8000/docs
- HTTPS local (optionnel) : `docker compose --profile https up -d`, puis https://localhost:8443
  avec `COOKIE_SECURE=true` dans `.env`.

Les migrations sont appliquées au démarrage de l'API. Pour les rejouer à la main :
`docker compose exec api python -m app.cli init-db`.

## Tests et qualité

```bash
docker compose exec api pytest -q --cov=app   # API, sur la base garage_test
docker compose exec api ruff check .
docker compose exec api mypy app

cd web
npm ci
npm run lint && npm run typecheck && npm test
```

La CI GitHub Actions (`.github/workflows/ci.yml`) rejoue les mêmes contrôles.

## Organisation du dépôt

```
api/            FastAPI : app/{models,schemas,routers,services,security}, alembic/, tests/
web/            Next.js : src/{app,components,lib,styles}, design/tokens.json, tests/
docs/agile/     Definition of Done, tableau, backlog, comptes rendus de sprint
docs/uml/       Modèle de données
infra/          Caddy (HTTPS local)
```

## Méthode et historique Git

- `main` : une version par fin de sprint, taguée `sprint-0` … `sprint-4`.
- `develop` : intégration continue des stories.
- `feature/<story>` : une branche par story, un commit par tâche du backlog
  (`feat(api): … [S8.1]`), fusionnée dans `develop` avec `--no-ff`.

Voir `docs/agile/` pour la Definition of Done, le backlog et les comptes rendus de sprint.
