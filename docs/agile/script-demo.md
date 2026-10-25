# Script de la démo — revue du 24 décembre 2026

Durée : **15 minutes**, questions comprises. Objectif : montrer au Product Owner le MVP complet
(version 1.0, tag `sprint-4`), du premier appel du client au paiement de la facture, avec les
deux rôles, et rappeler ce que chaque sprint a apporté.

## Rôles dans l'équipe

| Qui | Rôle pendant la démo |
| --- | --- |
| Scrum Master | ouvre la revue, tient le temps (alerte à 12 min), note les retours du PO |
| Développeur 1 (« Nadia », gérant) | pilote le poste d'accueil : navigateur à 1280 px, thème clair |
| Développeur 2 (« Karim », mécanicien) | pilote la tablette : navigateur à 1024 px, deuxième fenêtre |
| Développeur 3 | commente l'architecture et les garanties de la base quand on les montre |
| Développeur 4 | prêt pour le plan de secours (terminal ouvert sur le dépôt) |

## Préparation (la veille et 30 minutes avant)

```bash
docker compose up -d --build
(cd web && npm run e2e)                             # recette verte, AVANT la remise à zéro
docker compose exec api alembic downgrade base      # efface les factures et clients « Recette… »
docker compose exec api alembic upgrade head
docker compose exec api python -m app.cli seed     # le matin même : la journée est datée du jour
docker compose restart api web                      # connexions et pages repartent du nouveau schéma
```

Le seed est relancé **le 24 au matin** : la journée d'atelier, les retards et « Facturé
aujourd'hui » sont calculés par rapport à l'heure de la démo. La recette émet et paie de vraies
factures (immuables, elles prennent des numéros) et crée des clients « Recette… » qu'un seed ne
retire pas : elle passe donc **avant** la remise à zéro, jamais après, sinon la Toyota ne
recevrait pas le numéro `F-2026-003` annoncé à 8:30. Ouvrir à l'avance un onglet par écran pour
éviter la première compilation des pages en direct.

## Données de la démo (jeu de démonstration)

- comptes : `nadia@garage.test` (gérant), `karim@garage.test` (mécanicien), mots de passe du `.env` ;
- Peugeot 308 SW `GH-482-KL` de Claire Laurent (14 rue des Établis, 69003 Lyon) : OT du jour
  `OT-2026-003`, devis de la maquette **454,80 € TTC** accepté par téléphone à 9 h 40,
  historique avec deux interventions livrées ;
- Renault Clio V `FD-119-RT` de Moussa Diallo : devis de **612,40 € TTC** envoyé, « Devis à
  faire valider » au tableau de bord ;
- Toyota Yaris `HB-205-MZ` : intervention « Prêt », devis accepté, « Facture à établir » ;
- Dacia Sandero `GA-664-SN` : urgente, en retard (promise à 12 h 00) ;
- factures : `F-2025-001` payée par chèque (prestation de la veille de l'émission),
  `F-2026-001` payée par carte, `F-2026-002` (BMW du jour) payée en partie : reste 104,92 €.

## Déroulé (15 minutes)

| Minute | Écran | Ce qu'on montre | Ce qu'on dit |
| --- | --- | --- | --- |
| 0:00 | — | ouverture | Objectif du produit : remplacer le papier d'un garage indépendant. Cinq sprints, 36 points livrés (9, 10, 10 et 7), plus les mentions de la facture et la recette. |
| 0:45 | `/connexion` | connexion de Nadia | **Sprint 1 — accès** : argon2id, blocage après 5 échecs (on ne le déclenche pas en direct), cookie httpOnly, CSRF, menu selon le rôle. |
| 1:30 | Tableau de bord | indicateurs, Dacia en retard, « À traiter maintenant » : devis Clio à faire valider, facture Toyota à établir | **Sprint 3** a apporté ce tableau de bord (maquette 4) ; le sprint 4 y ajoute les devis à valider. |
| 2:30 | Champ « Rechercher » | `gh482kl`, puis `diallo`, puis `06 45 71` | **S1.3 Recherche** : nom sans accents, téléphone partiel, plaque sans tirets, numéros d'OT et de facture ; « Aucun résultat… » sur une faute de frappe. |
| 3:30 | Fiche client Claire Laurent | adresse, véhicule, historique de la Peugeot | **Sprint 1 — fiches** : doublon de téléphone signalé, immatriculation SIV unique ; adresse ajoutée au sprint 4 pour les factures. |
| 4:30 | `/planning` puis `/rendez-vous` | ponts du jour, colonne « À planifier » | **Sprint 2 — atelier** : pas de chevauchement sur un pont, garanti par la base (EXCLUDE). |
| 5:30 | Fiche `OT-2026-003` (Peugeot) | tâches, suivi horodaté, devis 379,00 HT / 75,80 TVA / **454,80 € TTC**, badge « Accepté » | **S4.1 et S4.2** : calcul au centime (même règle côté écran et côté API), statut du devis ; on ne modifie plus un devis envoyé, on le refuse et on en fait un nouveau. |
| 7:00 | Tablette (Karim, 1024 px) | « Mes travaux », OT de Karim, cases à cocher, « Terminer l'intervention » | **S3.2** : le mécanicien fait avancer le statut ; il ne voit ni montants ni coordonnées ; `/factures` lui répond 403. |
| 8:30 | Fiche OT Toyota (Nadia) | « Générer la facture » → confirmation → numéro `F-2026-003`, PDF | **S4.3** : numérotation sans trou, facture figée et immuable (triggers de la base), PDF avec mentions légales, adresse du client et date de la prestation. |
| 10:00 | Facture `F-2026-002` | paiements, reste 104,92 € ; essai à 200 € d'abord → « Le paiement dépasse le reste à payer (104,92 €). » ; paiement partiel de 50,00 € puis solde de 54,92 €, « Payée » (le formulaire disparaît) | **S4.4** : paiements partiels, trop-perçu refusé par l'API et par la base, aucune donnée de carte (terminal du garage). |
| 11:30 | Onglet Factures | filtres Impayées / Partielles / Payées, colonnes « Paiement » et « Reste à payer » | Suivi des encaissements pour le gérant ; une facture impayée le lendemain de son échéance porte « En retard » en toutes lettres (aucune facture de démonstration n'est en retard : on le dit, on ne le montre pas). |
| 12:00 | Terminal ou capture | recette Playwright verte (13 tests, mise en page à 1024 px comprise), 659 tests pytest, 196 tests Vitest | **Recette** : parcours gérant et mécanicien automatisés, accessibilité (clavier, un seul titre par page, focus visible, thème sombre). |
| 13:00 | — | questions du PO | Points ouverts : glisser-déposer du planning, SMS, stock, espace client, suppression des données sur demande (hors MVP). |

## Plan de secours

- **Une page répond 404** (Turbopack sous Docker Desktop) : `docker compose exec web touch
  "/app/src/app/(app)/<page>/page.tsx"`, ou `docker compose restart web` (30 s).
- **Données abîmées pendant la démo** (facture émise par erreur, paiement en trop…) : remettre
  la base à zéro (2 minutes) :

  ```bash
  docker compose exec api alembic downgrade base
  docker compose exec api alembic upgrade head
  docker compose exec api python -m app.cli seed
  docker compose restart api web
  ```

- **Compte bloqué** : relancer le seed (débloque les comptes de démonstration).
- **Panne de l'interface** : montrer l'API dans http://localhost:8000/docs (rôles, 403 du
  mécanicien) et les captures `sprint4-*.png` de la recette (tableau de bord, OT avec devis
  accepté, facture et paiements, recherche).
- **Panne complète de la machine** : dérouler les captures et le compte rendu du sprint,
  reprendre la démo sur la machine du développeur 4 (même dépôt, même `.env`).
