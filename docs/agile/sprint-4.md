# Sprint 4 — Devis, paiements, recherche et recette

## Revue de code
Plusieurs relecteurs indépendants (back et base de données, front et accessibilité, recette et
documentation, piste Git) ont remonté 12 constats sur S4.2, S1.3, S4.4 et la recette. Aucun
doublon : les deux constats de mise en page (onglet Factures et onglet Devis) sont distincts mais
ont été corrigés dans le même commit. Tous ont été vérifiés avant d'être traités sur
`fix/sprint-4-revue` : sonde SQL sur la base de test, plan d'exécution, mesures dans Chromium à
1024 et 1440 px en thème clair et sombre, lecture de l'historique Git. Chaque correction de code
a un test qui échouait avant elle (pytest, Vitest ou Playwright).

| Gravité | Story | Constat | Traitement |
| --- | --- | --- | --- |
| Majeur | S4.2 | Piste Git : des commits rouges dans `develop` et sur `feature/S4.3-mentions-facture`. Le test d'aller-retour des migrations (`26c9c73`) et le changelog « corrigé » (`038932d`) sont arrivés avant le correctif `80ecf11`, et la branche a été fusionnée dans `develop` à ce moment-là (`6eac1ba`). À ce commit, le downgrade de 0012 échouait (`UndefinedObject`, contrainte sans `op.f`) et `ruff` signalait `zip(..., strict=False)` : pytest et ruff étaient rouges. Les fusions `faf2123` et `934dabe` ont apporté le même test alors que 0015 avait le même défaut, corrigé seulement en `01cd167`. | Constat vérifié commit par commit (`git show <commit>:…`). L'historique n'est pas réécrit : les commits `26c9c73`, `038932d`, `6eac1ba`, `faf2123` et `934dabe` (et `80ecf11` pour ruff) sont rouges, et c'est noté ici. Cause : le test a été écrit et fusionné avant son correctif, et ruff n'a pas été relancé seul. La Definition of Done impose désormais de lancer pytest, ruff check, ruff format --check et mypy comme commandes séparées, chacune avec son code de sortie vérifié, avant chaque commit **et** avant chaque fusion. Une branche de correctif ne se fusionne qu'une fois son commit `fix(...)` fait. À reprendre en rétrospective. |
| Majeur | S4.4 | Onglet Factures à 1024 px : tableau de 1 172 px pour un cadre de 898. Le badge « Partiellement payée » est rogné, « Reste à payer » et le PDF sont hors de l'écran. La page entière défile aussi, à cause du `.sr-only` « Téléchargement » qui sort du `.table-wrap` non positionné. | Le modèle passe sous la plaque (`.cellule-empilee`) et la date d'émission sous le numéro. Les en-têtes « Numéro · émise le » et « Reste à payer » peuvent tenir sur deux lignes. `.table-wrap` est maintenant en `position: relative`. Le tableau mesure 898 px à 1024 px. À 1440 px, il dépassait aussi avec des noms longs (1 176 pour 1 134), ce qui est corrigé du même coup. Nouveau parcours Playwright `mise-en-page.spec.ts` à 1024 et 1440 px, thèmes clair et sombre : pas de défilement de page, tableau dans son cadre, numéros et plaques sur une ligne (`c3e7597`). |
| Mineur | S1.3 | Les jokers LIKE étaient échappés avant `unaccent`, qui change ensuite « ％ », « ﹪ », « ＿ » et « ＼ » en « % », « _ » et « \ ». Résultat : « ％％ » listait 20 clients et « l＿urent » trouvait « Laurent ». | L'échappement se fait désormais en SQL, sur la saisie déjà normalisée (`echapper_like_sql`). Cas pleine chasse ajoutés au test des jokers (`84caf0b`). |
| Mineur | S1.3 | La requête des clients ne pouvait pas utiliser les index trigrammes. Avec un `OR` entre le nom, le téléphone et un `IN` sur les véhicules, PostgreSQL faisait `Seq Scan on client`, même avec `enable_seqscan = off`. | Les identifiants viennent maintenant d'une `UNION` de trois branches (nom, téléphone, plaque), chacune servie par son index. Une saisie qui n'est ni un téléphone ni une plaque garde la seule condition du nom. La proposition « tout en UNION » a été adaptée : avec une seule branche, le planificateur choisissait la clé primaire. Test du plan (`EXPLAIN`) pour un nom, un téléphone et une plaque (`cb4f5f9`). |
| Mineur | S1.3 | « +33 (0)6 12 48 30 75 » ne trouvait rien : la saisie devenait « 00612483075 ». | Le 0 national écrit après « +33 » ou « 0033 » ne compte plus qu'une fois (« +33 06 … » est traité pareil). Cas ajoutés aux tests de lecture et de recherche (`0c1b18b`). |
| Mineur | S4.4 | Un paiement saisi dans la minute d'émission de la facture était refusé. Le formulaire envoie l'heure à la minute, alors que l'émission garde ses secondes, et le message affichait la même minute que la saisie. | La comparaison se fait à la minute. Un paiement saisi dans la minute d'émission est enregistré à l'instant de l'émission, jamais avant. La minute précédente reste refusée. Test pytest avec une émission à 14 h 47 min 40 s (`a350f59`). |
| Mineur | S4.4 | La date de réception d'un paiement et la date de décision d'un devis d'une année précédente s'affichaient sans l'année (« lun. 27 oct. à 9 h 30 » pour un chèque de 2025). | Nouveau `formatDateHeureOuAnnee` (même règle que `formatDateCourteOuAnnee`), utilisé pour `recu_le`, `envoye_le` et `decide_le`. Tests Vitest (`1a92695`). |
| Mineur | S4.2 | Onglet Devis à 1024 px : « OT-2026-016 » et « F-2026-006 » étaient coupés sur trois lignes, et « Non facturé » était rogné. | Numéros d'OT et de facture en `nowrap`, modèle sous la plaque. Même parcours Playwright (`c3e7597`). |
| Mineur | S1.3 | En-tête du tableau de bord : « Nouvelle intervention » passait sous le champ « Rechercher », même à 1440 px, alors que la maquette 4 les met sur une ligne. | Le champ a une largeur de 320 px (200 px au moins) au lieu d'un pourcentage mal résolu, et le bloc d'actions ne passe plus à la ligne. À 1440 px, champ et bouton sont sur la ligne du titre. À 1024 px, ils descendent ensemble sous le titre, à droite. Cas Playwright aux deux largeurs (`b7b2f11`). |
| Mineur | Recette | Les données « uniques » des tests e2e venaient des secondes écoulées plus un petit décalage. Deux fichiers lancés à 100 s d'écart pouvaient obtenir la même plaque (409), et le créneau du gérant revenait toutes les 600 s (409 de chevauchement). | L'identifiant d'exécution est tiré une fois au chargement (`E2E_EXECUTION` permet de le fixer). Les données en découlent sans l'horloge (`tests/e2e/donnees.ts`, testé par Vitest, collision reproduite avant correction). Le rendez-vous est pris sur le premier créneau libre du pont 3, lu par `GET /rendez-vous`. README à jour (`50176bd`). |
| Mineur | Recette | `docs/api.md` donnait `?confirmer=true` (ignoré par l'API, 409) au lieu de `?confirmer_doublon=true`, et affirmait que les dates sont « rendues en UTC ». | Paramètre corrigé dans les deux lignes. Formats décrits comme « ISO 8601 avec décalage horaire » (`bf4d8c1`). L'API n'a pas été changée pour sérialiser en UTC : l'interface lit déjà correctement les deux formes. |
| Mineur | Recette | Le script de la démo lançait la recette après la remise à zéro. Ses factures immuables restaient en base, et la Toyota ne recevait plus `F-2026-003`. L'essai à 200 € venait après le paiement qui solde la facture, alors que le formulaire disparaît à ce moment-là. Aucune facture de démonstration n'est « En retard ». | La recette passe avant downgrade / upgrade / seed. L'essai à 200 € vient avant le solde. « En retard » est expliqué mais pas montré. Nombres de tests à jour (`fb71d39`). La séquence a été rejouée : recette verte, puis base remise à zéro, factures `F-2025-001`, `F-2026-001`, `F-2026-002` et aucun client « Recette… ». |

### Constats rejetés
Aucun : les 12 constats décrivent des défauts réels. Trois propositions de correction ont été
adaptées plutôt que suivies telles quelles :
- index de recherche : pas d'`UNION` pour une saisie qui n'est qu'un nom (voir le tableau) ;
- dates de l'API : la documentation est corrigée, la sérialisation reste la même (un passage en
  UTC changerait toutes les réponses pour un gain nul côté interface) ;
- piste Git : l'historique n'est pas réécrit (commits déjà fusionnés dans `develop`), le
  constat est consigné et la Definition of Done est complétée.

### Observé pendant la revue, non traité
- Tableau de bord à 1440 px : le tableau « Interventions du jour » dépasse son cadre de 20 px
  (790 pour 770), et la colonne « Restitution » touche le bord. Ce défaut date du sprint 3 et ne
  figure dans aucun constat. À estimer au prochain affinage du backlog.
- Sous Docker Desktop, la route `/ordres/{id}/tablette` répond parfois 404 après un
  `docker compose restart web`, jusqu'à ce que sa page soit touchée dans le conteneur. C'est le
  défaut connu de Turbopack décrit dans le plan de secours de la démo.

Vérifications à la fin de la revue, toutes vertes :
- API : pytest (659 tests), ruff, ruff format et mypy strict ;
- web : ESLint, TypeScript, Vitest (196 tests) et build de production ;
- base : `alembic check`, et aller-retour `downgrade base` → `upgrade head` sur la base de test ;
- recette Playwright contre la pile de développement : 13 tests verts en une seule exécution,
  rejouée sur la même base ; la base de développement a ensuite été remise à zéro et seedée.
