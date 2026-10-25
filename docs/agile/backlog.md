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
| S8.2 | En tant que gérant, je gère les comptes de mes employés (nom, prénom, e-mail, mot de passe, rôle) afin de les créer, consulter, modifier ou désactiver | 5 | 5 |
| S8.3 | En tant que gérant, je m'inscris de façon autonome | 3 | 5 |
| S1.5 | En tant qu'utilisateur, je filtre chaque liste par une recherche : devis et factures, clients, véhicules, ordres de travail et employés | 3 | 5 |

**Sprint 5 « Comptes et recherche » (4 au 15 janvier 2027, 11 points, version 1.1.0).** S8.2
manquait au backlog du MVP : à l'affinage, les comptes des employés n'existaient qu'en ligne de
commande (`create-user`) et aucune story ne couvrait leur gestion dans l'application. L'écart a
été relevé après la revue du 24 décembre ; le PO a ajouté S8.2, puis S8.3 (inscription du
gérant) et S1.5 (recherche dans chaque liste), demandées à la même revue.

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

**S8.2 Comptes des employés** (absente du backlog du MVP, ajoutée après la revue du 24 décembre)
- Le gérant crée, consulte, modifie, désactive et réactive le compte d'un employé : prénom, nom,
  e-mail, mot de passe et rôle (gérant ou mécanicien).
- E-mail unique sans tenir compte de la casse ; mot de passe de 12 caractères au moins, haché
  en argon2id, jamais renvoyé par l'API.
- Un employé désactivé ne peut plus se connecter (« Identifiants invalides. ») et ses sessions
  ouvertes cessent de fonctionner dès la requête suivante.
- Le gérant ne peut ni se désactiver ni changer son propre rôle ; il reste toujours au moins
  un gérant actif, même avec deux changements simultanés.
- Le gérant réinitialise un mot de passe (le compte est aussi débloqué) et débloque un compte
  bloqué après 5 essais.
- Le mécanicien reçoit un 403 sur toutes les routes des comptes.

**S8.3 Inscription du gérant** — décision du PO : inscription ouverte, mais tout nouveau compte
reste en attente jusqu'à sa validation par un gérant actif.
- Le tout premier compte, quand aucun gérant actif n'existe (installation d'un garage), est
  créé actif avec le rôle gérant et sa session est ouverte ; deux inscriptions simultanées ne
  créent qu'un seul gérant actif.
- Sinon, la demande est enregistrée « En attente de validation » avec un message neutre ; un
  e-mail déjà connu reçoit exactement la même réponse, sans rien créer ni modifier.
- Un compte en attente ne peut pas se connecter ; après un mot de passe correct, le message dit
  que le compte attend la validation d'un gérant (rien n'est révélé sans le mot de passe).
- Le gérant valide le compte en choisissant son rôle, ou refuse la demande ; « Compte à valider »
  apparaît dans « À traiter maintenant ».
- Mot de passe de 12 caractères au moins ; jeton CSRF exigé ; nombre de demandes en attente
  limité (protection contre les abus).

**S1.5 Recherche dans les listes**
- Devis, factures, clients, véhicules, ordres de travail et employés ont chacun un champ de
  recherche filtré par l'API : la pagination et le total restent justes.
- Sans tenir compte des accents ni de la casse ; nombre de résultats annoncé ; message clair
  « Aucun … ne correspond à « xyz ». ».
- La saisie est gardée dans l'adresse (`?q=`) : retour arrière, avance et rechargement la
  conservent.
- Le mécanicien ne cherche que dans les listes qu'il voit déjà, jamais par un champ qu'il ne
  voit pas (ni téléphone ni e-mail de client).

**Mentions de la facture (revue du sprint 3, acceptée par le PO pour le sprint 4, hors
estimation)** — adresse du client sur sa fiche, figée dans la facture et imprimée sur le PDF
(art. 242 nonies A du CGI) ; date de fin de la prestation figée à l'émission et imprimée
« Prestation réalisée le jj/mm/aaaa » quand elle diffère de la date d'émission. Décision du
PO au sprint 4 : la fin de la prestation est le passage à « Prêt » (fin des travaux), à défaut
la clôture de l'OT ; les factures déjà émises restent telles quelles.

## Reporté après le MVP
Glisser-déposer dans le planning, modification et annulation de rendez-vous, rappels SMS et e-mail,
stock de pièces, espace client, paiement en ligne, statistiques, suppression des données sur demande (RGPD).
