# Sprint 2 — Atelier

**Dates** : 16 au 27 novembre 2026 · **Engagé** : 10 points · **Livré** : 10 points · **Tag** : `sprint-2`

## Objectif
L'atelier suit ses véhicules : le gérant ouvre un ordre de travail et planifie les ponts, le
mécanicien fait avancer ses interventions depuis la tablette, et chacun consulte l'historique d'un véhicule.

## Stories livrées
| Story | Pts | Branche | Résultat |
| --- | --- | --- | --- |
| S3.1 Ordre de travail | 3 | `feature/S3.1-ordre-travail` | numéro `OT-AAAA-nnn` sans trou (compteur verrouillé, testé en concurrence), véhicule obligatoire, tâches, mécanicien facultatif, fiche de l'OT (maquette 2) |
| S3.2 Statut et kanban | 2 | `feature/S3.2-statut-kanban` | une étape à la fois sans retour (409), « Prêt » si toutes les tâches sont faites, historique horodaté avec l'auteur, kanban « Suivi atelier », vue tablette (maquette 1), « Mes travaux » |
| S2.1 Rendez-vous | 3 | `feature/S2.1-rendez-vous` | date passée refusée, chevauchement refusé (service et contrainte `EXCLUDE`), créneaux adjacents acceptés, planning du jour par pont (maquette 3), journée de démonstration |
| S1.4 Historique | 2 | `feature/S1.4-historique` | interventions du plus récent au plus ancien, onglets accessibles, « Aucune intervention pour ce véhicule. » |

Migrations : `0006` (ordre_travail, tache_ot, compteur), `0007` (historique_statut), `0008` (pont,
rendez_vous). Aller-retour `downgrade base` → `upgrade head` vérifié, `alembic check` sans écart.

## Definition of Done
- [x] Un commit par tâche du backlog, branches fusionnées en `--no-ff`
- [x] API : 255 tests pytest (125 au sprint 1), ruff, mypy strict — verts
- [x] Web : 74 tests Vitest (38 au sprint 1), ESLint, TypeScript, build — verts
- [x] Règles d'accès testées (mécanicien : lecture des OT, du planning et de l'historique, statut et tâches ; jamais le téléphone ni l'e-mail du client ; 403 sur la création d'OT et de rendez-vous)
- [x] Concurrence testée sur deux connexions réelles (numérotation, verrou de l'OT, kilométrage)
- [x] Vérification dans le navigateur à 1024 px : vue tablette, planning, kanban, fiche OT
- [x] CHANGELOG à jour
- [ ] Tests verts à **chaque** commit : non tenu sur `f3cf17a` (voir l'écart de processus ci-dessous)

## Revue de code
Deux relecteurs indépendants (back/sécurité et front/design) ont remonté 7 constats sur S3.1, S3.2, S2.1 et S1.4, tous vérifiés et traités sur
`fix/sprint-2-revue` ; chaque correction de code a un test qui échouait avant elle :

| Gravité | Story | Constat | Traitement |
| --- | --- | --- | --- |
| Majeur | S3.2 | `PUT /ordres/{id}` ne verrouillait pas l'OT : OT « Prêt » avec une tâche ouverte, OT livré modifié, 500 en supprimant une tâche en cours de coche | verrou `FOR UPDATE` comme pour le statut et les tâches, tests sur deux connexions |
| Majeur | S3.2, S2.1, S1.4 | Planning, rendez-vous et historique du véhicule périmés après une action sur un OT | helper `rafraichirApresOrdre` pour toutes les écritures |
| Mineur | S3.1 | Deux ouvertures simultanées pouvaient faire reculer le kilométrage du véhicule | verrou du véhicule quand un kilométrage est relevé |
| Mineur | S2.1 | Dates extrêmes (`9999-12-31`, `0001-01-01`) : 500 | jours et instants bornés de 2000 à 2100, 422 « Date hors limites. » |
| Mineur | S2.1 | Un OT non livré dont le rendez-vous date d'un jour précédent disparaissait du planning | report en tête de son pont, charge = tâches restantes |
| Mineur | S3.2 | « Passer à « Prêt » » actif sur la fiche et le kanban malgré des tâches ouvertes | bouton désactivé, « Encore N tâches à terminer. » (même règle que la tablette) |
| Mineur | S2.1 | Piste Git : un commit avec un test en échec (voir ci-dessous) | consigné, DoD complétée |

### Écart de processus : un commit avec un test rouge
Le commit `f3cf17a` (« feat(api): journée de démonstration … [S2.1] ») ajoute la journée de
démonstration au compte rendu du seed (25 lignes au lieu de 12) sans mettre à jour l'assertion de
`test_seed_cree_les_comptes_de_demo_et_reste_idempotent` ; la correction n'arrive qu'au commit
suivant, `42f1a6d`. La règle « tests verts à chaque commit » n'a donc pas été tenue sur ce commit.
L'historique n'est pas réécrit (branche déjà fusionnée dans `develop`).

Cause : `pytest` lancé à travers un pipe (`pytest | tail`), dont le code de sortie est celui du
dernier programme. Action : la Definition of Done demande désormais de lancer `pytest` sans pipe
(ou avec `set -o pipefail`) avant chaque commit et de vérifier son code de sortie.

## Démo
1. `nadia@garage.test` (gérant), « Suivi atelier » : 4 colonnes, la Dacia Sandero **Urgent** en tête
   des « En cours » ; « Passer à « Prêt » » est désactivé avec « Encore 1 tâche à terminer. ».
2. « Planning atelier » : les 3 ponts du jour avec leur charge, la colonne « À planifier » ; jour
   suivant avec « › ».
3. « Rendez-vous » : un rendez-vous sur le Pont 1 à 9 h 00 → refusé « Le Pont 1 est déjà occupé de
   8 h 00 à 10 h 30. » ; à 11 h 30 sur le Pont 3, juste après le créneau 9 h 30 – 11 h 30 →
   accepté (créneaux adjacents) ; date d'hier → refusée.
4. Nouvel ordre de travail sur un véhicule → numéro `OT-2026-010`, suivi « Véhicule déposé ».
5. `karim@garage.test` (mécanicien) : « Mes travaux » (Peugeot 308, Golf 7) → vue tablette de la
   Peugeot, cocher les deux tâches restantes → « Terminer l'intervention » s'active → statut « Prêt »,
   le suivi indique « par Karim ». La fiche ne montre ni téléphone ni e-mail du client.
6. Fiche véhicule GH-482-KL, onglet « Historique » : `OT-2026-003` (en cours), puis `OT-2026-001`
   (avril) et `OT-2025-001` (l'an dernier), de la plus récente à la plus ancienne.

## Rétrospective
- **Bien** : les règles sensibles sont garanties par la base en plus du code (contrainte
  `EXCLUDE` sur les ponts, compteur verrouillé) ; la revue a trouvé deux vraies courses
  (verrou du `PUT`, kilométrage) reproduites sur la pile avant d'être corrigées.
- **À améliorer** : un commit est parti avec un test rouge, masqué par un pipe ; la DoD est
  complétée (`pytest` sans pipe ou avec `pipefail`).
- **À améliorer** : sur Docker Desktop pour Windows, le serveur de dev Turbopack a parfois manqué
  la route `/ordres/[id]/tablette` (404 jusqu'à ce que le fichier soit modifié), alors que le build
  de production la contient. Action : documenter le contournement dans le README (toucher le fichier
  ou vider le volume `web_next`) et le vérifier avant la recette du sprint 4.
- **Décision métier** : un mécanicien peut faire avancer n'importe quel OT (l'historique garde
  l'auteur) ; une fois « Prêt », un OT n'accepte plus de tâche nouvelle ni rouverte.
