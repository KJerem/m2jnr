# Sprint 2 — Atelier

> Document ouvert pendant la revue de code ; objectif, démo et rétrospective sont complétés à la
> clôture du sprint.

## Revue de code
Les relecteurs ont remonté 7 constats sur S3.1, S3.2, S2.1 et S1.4, tous vérifiés et traités sur
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
