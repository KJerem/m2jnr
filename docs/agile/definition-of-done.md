# Definition of Done

Une story est « terminée » quand **toutes** les cases sont cochées. Le testeur du binôme vérifie la
liste avant le passage en colonne « Terminé ».

## Code
- [ ] Le code est sur une branche `feature/<id-story>-<slug>` issue de `develop`.
- [ ] Un commit par tâche du backlog, au format Conventional Commits, avec l'identifiant de la story (`[S1.1]`).
- [ ] `ruff check`, `ruff format --check` et `mypy app` passent côté API.
- [ ] `npm run lint` et `npm run typecheck` passent côté web.
- [ ] Aucun secret ni donnée réelle dans le dépôt (seulement `.env.example` et des données fictives).

## Tests
- [ ] Les cas de test listés dans la story sont automatisés (pytest pour les règles métier, Vitest pour l'interface).
- [ ] `pytest` et `npm test` passent en local et en CI.
- [ ] Les tests passent **à chaque commit** : `pytest` est lancé sans pipe (ou avec `set -o pipefail`)
      avant de valider, et son code de sortie est vérifié.
- [ ] Les règles d'accès sont testées (403 pour un rôle non autorisé).

## Produit
- [ ] Les critères d'acceptation sont vérifiés à la main dans l'application lancée par `docker compose up`.
- [ ] L'écran respecte le design system Établi : tokens, `StatusBadge` avec pastille et mot, `Plate`, boutons de 44 px.
- [ ] Navigation au clavier possible, focus visible, contraste conforme dans les thèmes clair et sombre.
- [ ] L'écran est utilisable sur tablette (1024 px de large).
- [ ] Les messages d'erreur sont en français, clairs et rattachés au champ concerné.

## Intégration
- [ ] La branche est fusionnée dans `develop` avec `git merge --no-ff`.
- [ ] Le `CHANGELOG.md` mentionne la story.
- [ ] Le Product Owner a validé la story lors de la revue de sprint.
