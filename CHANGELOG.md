# Journal des modifications

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Une entrée par sprint.

## [Non publié]

### Ajouté
- S3.1 Ordre de travail : ouverture d'un OT par le gérant, numéro `OT-AAAA-nnn` unique et consécutif (compteur verrouillé dans la transaction, sans trou même en cas d'annulation ou de création simultanée, année de Paris), véhicule obligatoire, demande du client, diagnostic, tâches prévues, mécanicien facultatif, kilométrage d'entrée reporté sur le véhicule, restitution prévue ; liste filtrée par statut, formulaire avec lignes de tâches dynamiques, fiche de l'OT (maquette du détail), bouton « Nouvel ordre de travail » sur la fiche véhicule ; coordonnées du client réservées au gérant.
- S3.2 Statut et kanban : statuts « En attente » → « En cours » → « Prêt » → « Livré », une étape à la fois sans retour (409 sinon), « Prêt » seulement quand toutes les tâches sont terminées, chaque changement horodaté avec son auteur dans le suivi de l'OT (historique créé dès l'ouverture), tâches cochées par le gérant ou le mécanicien ; page « Suivi atelier » en kanban avec un bouton « Passer à … » par carte, vue tablette atelier (grandes cases, « Terminer l'intervention »), « Mes travaux » à l'accueil du mécanicien.

## [sprint-1] — Accès et fiches (2 au 13 novembre 2026)

### Ajouté
- S8.1 Connexion et rôles : connexion par e-mail et mot de passe (argon2id), blocage 15 min après 5 échecs avec l'heure de déblocage, session en cookie httpOnly, protection CSRF, accès du mécanicien refusé sur les devis et les factures, page `/connexion` et menu selon le rôle, comptes de démonstration (`python -m app.cli seed`) et `create-user`.
- S1.1 Fiche client : création, modification et liste paginée des clients (gérant), nom et téléphone obligatoires, téléphone français normalisé, alerte de doublon de téléphone avec confirmation, consentement aux rappels explicite.
- S1.2 Fiche véhicule : véhicule rattaché à un client existant, immatriculation SIV normalisée et unique (casse et tirets ignorés), kilométrage entier positif, fiche véhicule lisible par le mécanicien, clients et véhicules de démonstration des maquettes.

### Corrigé
- Revue du sprint 1 : un compte désactivé n'est plus jamais bloqué (même réponse qu'un e-mail inconnu) ; la transaction est validée avant l'envoi de la réponse ; chiffres non ASCII refusés en 422 pour le téléphone et l'immatriculation ; identifiants et numéro de page hors limites en 404 ou 422 au lieu de 500 ; contraintes CHECK renommées sans double préfixe (migration 0005) ; relancer le seed débloque les comptes de démonstration ; la fenêtre de doublon rend le focus au bouton d'envoi ; la déconnexion mène exactement à `/connexion` ; le proxy exclut tout `/_next` ; cibles de 44 px pour la déconnexion, le thème et la pagination.

## [sprint-0] — Initiation (26 au 30 octobre 2026)

### Ajouté
- Dépôt Git, branches `main` et `develop`, conventions de commit.
- Environnement Docker : PostgreSQL, base de test, API FastAPI, interface Next.js, HTTPS local (Caddy).
- Migrations Alembic (extensions citext, btree_gist, pg_trgm) et commande `init-db`.
- Modèle de données UML (`docs/uml/modele-donnees.md`).
- Gabarit d'interface au design system Établi : menu par rôle, thème clair et sombre, pages 403 et 404.
- Tests : pytest sur base dédiée, Vitest, intégration continue GitHub Actions.
- Definition of Done, tableau d'équipe (WIP = 2) et backlog.
