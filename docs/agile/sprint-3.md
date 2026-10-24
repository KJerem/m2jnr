# Sprint 3 — Facturation, MVP complet

**Dates** : 30 novembre au 11 décembre 2026 · **Engagé** : 10 points · **Livré** : 10 points · **Tag** : `sprint-3`

## Objectif
Le garage chiffre et facture : le gérant établit le devis d'un ordre de travail, calculé
automatiquement, puis émet une facture PDF numérotée sans trou et non modifiable. Le tableau de bord
lui donne la journée de l'atelier d'un coup d'œil. Le parcours du MVP est complet, du client à la facture.

## Stories livrées
| Story | Pts | Branche | Résultat |
| --- | --- | --- | --- |
| S4.1 Devis | 5 | `feature/S4.1-devis` | lignes pièces et main-d'œuvre, HT, TVA 20 % et TTC en centimes (arrondi au demi-centime supérieur, identique côté API et côté écran), quantité nulle, négative ou à plus de 2 décimales refusée, gérant seul ; section « Devis — pièces & main-d'œuvre » de la fiche OT (maquette 2), onglets « Devis & factures » |
| S4.3 Facture PDF | 5 | `feature/S4.3-facture-pdf` | numéro `F-AAAA-nnn` sans trou (compteur verrouillé, testé en concurrence), client, véhicule, garage et lignes figés à l'émission, triggers PostgreSQL d'immuabilité (UPDATE, DELETE, TRUNCATE, INSERT après coup), PDF reportlab avec mentions légales, devis verrouillé une fois facturé |
| Tableau de bord gérant | — | `feature/tableau-de-bord` | écran de la maquette 4, hors estimation : 5 indicateurs, interventions du jour filtrables, arrivées prévues, « À traiter maintenant » ; rafraîchi toutes les minutes et après chaque action |

Migrations : `0009` (devis, ligne_devis), `0010` (facture, ligne_facture, triggers), `0011`
(lignes de facture figées). Aller-retour `downgrade base` → `upgrade head` vérifié, `alembic check` sans écart.

Les trois indicateurs de la maquette que l'application ne suit pas (attente pièces, clients sur
place, clients prévenus) sont remplacés par des données réelles : en retard, rendez-vous du jour,
prêts à restituer. Le champ de recherche de l'en-tête arrive avec S1.3 (sprint 4).

## Definition of Done
- [x] Un commit par tâche du backlog, branches fusionnées en `--no-ff`
- [x] API : 444 tests pytest (255 au sprint 2), ruff, mypy strict — verts, pytest lancé sans pipe
- [x] Web : 132 tests Vitest (74 au sprint 2), ESLint, TypeScript, build — verts
- [x] Critères d'acceptation : 168,00 € TTC, maquette 454,80 € TTC, quantité ≤ 0 refusée, mécanicien 403 sur devis, factures, PDF et tableau de bord, aucun montant dans ce qu'il peut lire
- [x] Facture : totaux identiques au devis, numéros continus, refus de la base vérifié en SQL direct, PDF lu avec pypdf (mentions, montants, caractères)
- [x] Vérification dans le navigateur à 1024 px, thèmes clair et sombre
- [x] CHANGELOG à jour
- [ ] Une tâche par commit : non tenu sur `ba4b16c` et `603ebaf` (correctifs livrés dans des commits `test:`, voir la revue)

## Revue de code
Plusieurs relecteurs indépendants (back et sécurité, PDF et conformité, front et accessibilité) ont
remonté 13 constats sur S4.1, S4.3 et le tableau de bord. Deux portaient sur le même défaut (police
du PDF) et ont été fusionnés : il reste 12 constats distincts. Tous ont été vérifiés (reproduits sur
la pile de développement, dans le navigateur ou par lecture du code) puis traités sur
`fix/sprint-3-revue`. Chaque correction de code a un test qui échouait avant elle.

| Gravité | Story | Constat | Traitement |
| --- | --- | --- | --- |
| Majeur | S4.3 | PDF de la facture : tout caractère absent de WinAnsi sortait en carré noir, y compris dans le nom du client (« ■ukasz Dvo■ák-Nguy■n »), la désignation, la marque et le modèle (deux constats fusionnés) | police DejaVu Sans 2.37 (normal et gras, licence jointe) livrée dans `api/app/polices`, enregistrée auprès de reportlab et incorporée au PDF, qui reste invariant ; test pypdf avec « Łukasz Ştefan Dvořák-Nguyễn », « Škoda Octavia Ő », « Ø 5 mm ≤ 3 bar → kit Ő » (`c31ba41`) |
| Majeur | S4.1 | Éditeur du devis : le focus clavier tombait sur `<body>` à l'ouverture (le bouton actionné disparaît), après « Annuler » et après « Enregistrer le devis » | focus sur le type de la ligne ajoutée (ou de la première ligne) à l'ouverture, puis sur « Modifier le devis », à défaut « Ajouter une ligne » ou le titre de la section, à la fermeture ; tests Vitest sur `document.activeElement`, vérifié dans Chromium (`9c5b9ae`) |
| Mineur | S4.3 | Focus perdu après la confirmation de « Générer la facture » : le bouton de retour de la fenêtre disparaît avec l'émission | focus sur « Télécharger le PDF », action suivante du nouvel état ; test Vitest (`9c5b9ae`) |
| Mineur | S4.1 | La quantité acceptait « 1e3 », « 1_0 », « +2 », « １ », que l'interface refuse, et un nombre JSON comme 1.0000000000000001, déjà arrondi en flottant avant toute lecture (« jamais arrondie en silence » non tenu) | seule la forme de l'interface est lue (chiffres ASCII, virgule ou point) ; nombre JSON à virgule refusé, 422 « Quantité décimale à envoyer en texte, par exemple « 0,5 ». », entier JSON accepté ; cas ajoutés au test paramétré (`9a5c82b`) |
| Mineur | S4.1 | Un caractère NUL dans une désignation ou une référence (et dans tout texte saisi, défaut antérieur au sprint) provoquait une erreur 500 | validateur commun `SansControle` sur les textes libres (fiche client, véhicule, OT, tâches, rendez-vous, lignes de devis) : 422 « Caractère non autorisé. », tabulation et retours à la ligne permis ; connexion : « Identifiants invalides. » sans requête (`50c565b`) |
| Mineur | S4.3 | Le downgrade de 0010 gardait le compteur `FACTURE` : après un aller-retour, la numérotation reprenait avec un trou | `DELETE FROM compteur WHERE type = 'FACTURE'` dans le downgrade ; test qui exécute le downgrade dans une transaction annulée (`84ac076`) |
| Mineur | S4.3 | Immuabilité incomplète : un `INSERT` dans `ligne_facture` était accepté sur une facture émise (une ligne de 1 000,00 € paraissait dans le PDF, totaux inchangés) | migration `0011` : la création d'une facture note son identifiant dans un paramètre local à la transaction, un `INSERT` de ligne pour une autre facture est refusé (`ET001`) ; test sur deux transactions validées (`e6cde52`) |
| Mineur | S4.1 | « Devis & factures » : après l'onglet Factures, le lien du menu ramenait l'adresse sur `/devis` mais gardait l'onglet Factures (page réutilisée, état local) | onglet déduit de `usePathname`, que Next.js synchronise avec `replaceState` ; test Vitest, vérifié dans Chromium (clic, menu, flèches) (`0b14634`) |
| Mineur | S4.1 | L'onglet Devis affichait « ven. 24 oct. » pour un devis de 2025, sans l'année | `formatDateCourteOuAnnee` partagé dans `lib/format`, utilisé par les deux onglets ; test Vitest (`6401799`) |
| Mineur | S4.1 | À 1024 px, le type de ligne affichait « Main-d'œuvr » (dernière lettre sous le chevron) | colonne « Type » de 168 px au moins, mesurée dans Chromium en thème clair et sombre ; test de contrat sur la grille (`74f420d`) |
| Mineur | S4.3 | Mentions obligatoires absentes du PDF : adresse du client, date de la prestation quand la facture est émise après la livraison | écart de conformité hors du périmètre de la story (le brief définissait le client figé sans adresse, et la fiche client n'en a pas) : inscrit au backlog « À planifier », à estimer et à prioriser par le Product Owner avant le sprint 4 |
| Mineur | S4.3 | Piste Git : du code de production livré dans des commits `test:` (`ba4b16c` modifie `pdf_facture.py`, `603ebaf` modifie `DevisOrdre.tsx`), une tâche par commit non respectée | consigné ; l'historique n'est pas réécrit (branches déjà fusionnées dans `develop`) ; la Definition of Done demande désormais un commit `fix(api)` ou `fix(front)` séparé, avant le commit `test:`, pour tout correctif découvert en écrivant les tests ; à reprendre en rétrospective |

### Constats rejetés
Aucun : les 13 constats décrivaient des défauts réels. Deux propositions de correction ont été
adaptées plutôt que suivies telles quelles :
- immuabilité des lignes : le test proposé sur `xmin` de la facture ne tient pas avec les points de
  sauvegarde (la facture est insérée dans un `begin_nested()`, son `xmin` est celui de la
  sous-transaction alors que `pg_current_xact_id()` renvoie la transaction principale) ; le
  paramètre local à la transaction, annulé avec le point de sauvegarde, donne la même garantie.
  Le contrôle différé « somme des lignes = total HT », proposé en option, n'a pas été ajouté :
  l'`INSERT` étant refusé, il n'aurait rien de plus à vérifier ;
- polices du PDF : DejaVu est livrée dans le dépôt plutôt qu'installée par `fonts-dejavu-core` dans
  l'image, pour que le PDF ne dépende ni de l'image ni du réseau au moment du build.

Vérifications à la fin de la revue : pytest (444 tests), ruff, ruff format, mypy strict, ESLint,
TypeScript, Vitest (132 tests), build de production, `alembic check` et aller-retour
`downgrade base` → `upgrade head` sur la base de test — verts.

## Démo
1. `nadia@garage.test` : le tableau de bord « Atelier — … » (7 véhicules, 1 prêt à restituer, la
   Dacia en retard après 12 h 00, « Facturé aujourd'hui » 154,92 € TTC), « À traiter maintenant » :
   « Facture à établir » pour la Toyota Yaris.
2. Fiche `OT-2026-003` (Peugeot 308 SW) : le devis de la maquette, 379,00 € HT, 75,80 € de TVA,
   **454,80 € TTC** ; « Modifier le devis », ajouter une ligne 2 × 40,00 € → totaux recalculés en
   direct ; quantité « 0 » → « La quantité doit être supérieure à 0. » ; « Générer la facture »
   désactivé, « Disponible quand l'intervention est « Prêt ». ».
3. Cas du backlog : sur un OT neuf, devis 2 pièces à 40,00 € + 1 h à 60,00 € → 140,00 € HT,
   28,00 € de TVA, 168,00 € TTC.
4. Fiche `OT-2026-006` (Toyota, « Prêt ») : « Générer la facture » → confirmation → `F-2026-003`,
   devis en lecture seule, « Télécharger le PDF » (mentions légales, échéance à 30 jours,
   pénalités, indemnité de 40 €).
5. « Devis & factures », onglet Factures : `F-2025-001`, `F-2026-001` à `F-2026-003`, sans trou.
6. `karim@garage.test` : pas d'entrée « Devis & factures », fiche OT sans devis ni montant, `/factures` → page 403.

## Rétrospective
- **Bien** : les montants sont des entiers du début à la fin, avec une seule règle d'arrondi écrite
  deux fois (Python, TypeScript) et testée sur les mêmes cas ; l'immuabilité de la facture est
  garantie par la base, pas seulement par l'API. La revue « facturation » a recalculé les montants
  de son côté et trouvé deux défauts que les tests ne voyaient pas (police du PDF, INSERT de ligne).
- **À améliorer** : des correctifs trouvés en écrivant les tests sont partis dans les commits
  `test:` ; la DoD demande désormais un commit `fix(...)` séparé.
- **À améliorer** : un test Vitest du sprint 1 échouait une fois sur deux (saisie lente dans jsdom) ;
  corrigé pour toute la suite (`userEvent` sans délai, délai de test global de 20 s) au lieu de
  rallonges bloc par bloc.
- **Incident** : la limite d'usage de l'outil a interrompu la revue une fois ; elle a été relancée
  depuis la reprise du workflow, sans refaire l'implémentation.
- **Décision pour le sprint 4** : la revue a relevé deux mentions de facture manquantes (adresse du
  client, date de la prestation, art. 242 nonies A du CGI). Les factures conformes faisant partie
  des contraintes du projet, elles sont ajoutées au sprint 4 en complément de S4.3.
