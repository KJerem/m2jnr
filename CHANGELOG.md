# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Une entrée par sprint.

## [Non publié]

### Ajouté
- S8.1 Connexion et rôles : connexion par e-mail et mot de passe (argon2id), blocage 15 min après 5 échecs avec l'heure de déblocage, session en cookie httpOnly, protection CSRF, accès du mécanicien refusé sur les devis et les factures, page `/connexion` et menu selon le rôle, comptes de démonstration (`python -m app.cli seed`) et `create-user`.
- S1.1 Fiche client : création, modification et liste paginée des clients (gérant), nom et téléphone obligatoires, téléphone français normalisé, alerte de doublon de téléphone avec confirmation, consentement aux rappels explicite.

## [sprint-0] — Initiation (26 au 30 octobre 2026)

### Ajouté
- Dépôt Git, branches `main` et `develop`, conventions de commit.
- Environnement Docker : PostgreSQL, base de test, API FastAPI, interface Next.js, HTTPS local (Caddy).
- Migrations Alembic (extensions citext, btree_gist, pg_trgm) et commande `init-db`.
- Modèle de données UML (`docs/uml/modele-donnees.md`).
- Gabarit d'interface au design system Établi : menu par rôle, thème clair et sombre, pages 403 et 404.
- Tests : pytest sur base dédiée, Vitest, intégration continue GitHub Actions.
- Definition of Done, tableau d'équipe (WIP = 2) et backlog.
