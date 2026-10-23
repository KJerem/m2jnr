# Backlog du MVP

Estimation en points (suite de Fibonacci). Ordre imposé par les dépendances : connexion et rôles,
puis fiches client et véhicule, puis atelier et rendez-vous, puis devis, puis facture.

| Id | Story | Pts | Sprint |
| --- | --- | --- | --- |
| S8.1 | En tant qu'employé, je me connecte avec mon rôle (gérant ou mécanicien) | 5 | 1 |
| S1.1 | En tant que gérant, je crée et modifie la fiche d'un client | 2 | 1 |
| S1.2 | En tant que gérant, je rattache un véhicule à un client | 2 | 1 |
| S3.1 | En tant que gérant, j'ouvre un ordre de travail pour un véhicule | 3 | 2 |
| S3.2 | En tant que mécanicien, je fais avancer le statut d'un ordre de travail | 2 | 2 |
| S2.1 | En tant que gérant, je planifie un rendez-vous sur un pont | 3 | 2 |
| S1.4 | En tant que mécanicien, je consulte l'historique des interventions d'un véhicule | 2 | 2 |
| S4.1 | En tant que gérant, je crée un devis calculé automatiquement (HT, TVA, TTC) | 5 | 3 |
| S4.3 | En tant que gérant, je génère une facture PDF numérotée sans trou | 5 | 3 |
| S4.2 | En tant que gérant, je suis le statut d'un devis | 2 | 4 |
| S1.3 | En tant que gérant, je recherche un client ou un véhicule | 2 | 4 |
| S4.4 | En tant que gérant, je suis les paiements d'une facture | 3 | 4 |

## Critères d'acceptation

**S8.1 Connexion et rôles**
- E-mail et mot de passe corrects : accès à l'application avec le menu de son rôle.
- Mauvais mot de passe : message « Identifiants invalides », sans dire lequel est faux.
- 5 échecs consécutifs : compte bloqué 15 minutes, message avec l'heure de déblocage.
- Le mécanicien reçoit un 403 sur les devis, les factures et la gestion des clients.
- Les requêtes qui modifient des données exigent un jeton CSRF valide.

**S1.1 Fiche client**
- Nom et téléphone obligatoires, e-mail facultatif mais valide ; consentement aux rappels explicite.
- Un téléphone déjà connu déclenche une alerte de doublon ; le gérant peut confirmer la création.

**S1.2 Fiche véhicule**
- Immatriculation unique (casse et tirets ignorés), au format SIV `AA-123-AA`.
- Kilométrage entier positif ou nul ; le véhicule est toujours rattaché à un client existant.

**S3.1 Ordre de travail**
- Numéro automatique `OT-AAAA-nnn`, unique et consécutif ; impossible sans véhicule.
- L'OT porte la demande du client, le diagnostic, les tâches prévues et éventuellement un mécanicien.

**S3.2 Statut et kanban**
- Transitions À faire → En cours → Terminé → Livré, une étape à la fois, sans retour.
- Chaque changement est horodaté avec son auteur et visible dans le suivi de l'OT.

**S2.1 Rendez-vous**
- Date, heure, durée, motif, pont et véhicule obligatoires.
- Refus d'une date passée et de deux rendez-vous qui se chevauchent sur le même pont.

**S1.4 Historique**
- Interventions du véhicule de la plus récente à la plus ancienne ; « Aucune intervention » si vide.

**S4.1 Devis**
- Lignes pièces et main-d'œuvre ; HT, TVA 20 % et TTC calculés en centimes, sans erreur d'arrondi.
- Exemple : 2 pièces à 40 € + 1 h à 60 € = 140,00 € HT, 28,00 € de TVA, 168,00 € TTC.
- Quantité nulle ou négative refusée ; accès réservé au gérant.

**S4.3 Facture PDF**
- Numéro `F-AAAA-nnn` continu, sans trou ; facture non modifiable une fois créée.
- PDF avec mentions légales et totaux identiques au devis.

**S4.2 Statut du devis** — brouillon → envoyé → accepté ou refusé ; seul un devis accepté est facturable.

**S1.3 Recherche** — par nom, téléphone ou immatriculation ; message clair si aucun résultat.

**S4.4 Suivi des paiements** — paiements partiels, solde restant, statut payé ; trop-perçu refusé.

## Reporté après le MVP
Glisser-déposer dans le planning, modification et annulation de rendez-vous, rappels SMS et e-mail,
stock de pièces, espace client, paiement en ligne, statistiques, suppression des données sur demande (RGPD).
