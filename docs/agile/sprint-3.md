# Sprint 3 — Facturation

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
