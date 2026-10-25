# Sprint 5 — Comptes et recherche (version 1.1.0)

**Dates** : 4 au 15 janvier 2027 · **Engagé** : 11 points · **Livré** : 11 points · **Tags** : `sprint-5`, `v1.1.0`

## Contexte
Après la revue du 24 décembre, le Product Owner a signalé une story du MVP absente du backlog :
la gestion des comptes des employés par le gérant. Il a demandé en plus l'inscription autonome
du gérant et une recherche dans chaque liste. Ce sprint, hors du calendrier initial, les livre en
version 1.1.0 sans toucher à l'historique de la 1.0.0.

**Écart d'affinage** : la story S8.2 aurait dû naître de S8.1 (connexion et rôles) lors de
l'affinage du sprint 1 : qui crée les comptes que S8.1 protège ? Le seed et la commande
`create-user` masquaient le besoin. Action : pour chaque story « rôles et accès », se demander
qui administre les comptes, comment ils naissent et comment ils disparaissent.

## Objectif
Le gérant administre seul l'équipe (créer, consulter, modifier, désactiver un compte), un
nouveau gérant s'inscrit sans intervention technique sous le contrôle d'un gérant existant, et
chaque liste se filtre par une recherche.

## Stories livrées
| Story | Pts | Branche | Résultat |
| --- | --- | --- | --- |
| S8.2 Comptes des employés | 5 | `feature/S8.2-comptes-employes` | prénom, nom, e-mail, mot de passe (12 caractères, argon2id, jamais renvoyé) et rôle ; création, fiche, modification, réinitialisation du mot de passe, déblocage, désactivation et réactivation ; toujours au moins un gérant actif (verrou sur les gérants), pas d'action sur soi-même ; sessions coupées à la désactivation et à la réinitialisation ; OT d'un mécanicien désactivé signalés « Mécanicien à affecter » |
| S8.3 Inscription du gérant | 3 | `feature/S8.3-inscription` | `POST /auth/register` et page `/inscription` ; premier compte du garage actif et connecté (verrou consultatif contre deux premières inscriptions simultanées), les suivants en attente de validation par un gérant, qui choisit le rôle ou refuse ; même réponse pour une adresse déjà connue, et refus générique pour un compte en attente : aucune énumération des comptes ; 20 demandes en attente au plus ; « Compte à valider » au tableau de bord |
| S1.5 Recherche dans les listes | 3 | `feature/S1.5-recherche-listes` | paramètre `q` sur clients, véhicules, ordres, devis, factures et employés (sans accents ni casse, jokers pris à la lettre, filtré dans la requête paginée) ; composant de recherche commun gardé dans l'adresse (rechargement, retour arrière) ; nouvelle liste des véhicules (onglet du gérant, entrée du mécanicien) ; le mécanicien ne cherche jamais par téléphone ni e-mail |

Migrations : `0016` (prénom, statut du compte, validation et désactivation), `0017` (sessions
valables depuis). Aller-retour de toute la chaîne sur la base de test, `alembic check` sans écart.

## Definition of Done
- [x] Un commit par tâche du backlog, branches fusionnées en `--no-ff`
- [x] API : 846 tests pytest (659 au sprint 4), ruff, mypy strict — verts, pytest lancé sans pipe
- [x] Web : 239 tests Vitest (196 au sprint 4), ESLint, TypeScript, build — verts
- [x] Recette Playwright : 18 tests verts sur le build de production
- [x] Critères d'acceptation des trois stories, dont : compte désactivé refusé et session coupée à la requête suivante, dernier gérant protégé, inscription en attente validée avec choix du rôle, recherche dans chaque liste avec message quand rien ne correspond, mécanicien 403 sur la gestion des comptes
- [x] Vérification dans le navigateur à 1024 et 1440 px, thèmes clair et sombre, console sans erreur
- [x] README, `docs/api.md`, modèle de données, script de la démo et CHANGELOG à jour
- [ ] Une tâche par commit : le `afterAll` de nettoyage de la recette est arrivé dans un commit de focus (`0c0415a`), signalé dans `2a338ff`

## Revue de code
Plusieurs relecteurs indépendants (sécurité et API, front et accessibilité, recette) ont remonté
14 constats sur S8.2, S8.3, S1.5 et la recette. Après dédoublonnage, il en reste 11 : la
réactivation qui rend vie aux sessions a été signalée deux fois, comme les essais de mot de passe
illimités sur un compte en attente. Ce second constat découle de l'énumération des comptes par
l'inscription et a reçu le même correctif. Le constat « filtres des Employés gardés au retour sur
/employes » a la même cause que la perte de la recherche au retour arrière ; un seul correctif
traite les deux. Chaque constat a été vérifié avant d'être traité sur `fix/sprint-5-revue` :
lecture du code, reproduction par un test sur la base de test ou dans jsdom, puis Playwright en
mode démo de production. Chaque correction a un test qui échouait avant elle (pytest, Vitest ou
Playwright).

| Gravité | Story | Constat | Traitement |
| --- | --- | --- | --- |
| Majeur | S8.3 | Énumération des comptes : l'inscrit choisit le mot de passe. `POST /auth/register` avec une adresse puis `POST /auth/login` avec ce mot de passe répondait 401 si l'adresse avait déjà un compte, 403 `compte_en_attente` si elle était libre. Doublon : un compte en attente acceptait un nombre illimité d'essais, sans compteur ni blocage, et le 403 confirmait le bon mot de passe. Un attaquant pouvait donc deviner en ligne le mot de passe d'une demande de gérant avant qu'elle soit validée. | Un compte en attente est refusé comme une adresse inconnue : 401 « Identifiants invalides. » avec ou sans le bon mot de passe, hash factice, aucun compteur. Il n'y a plus d'oracle, donc plus besoin de compteur. Tests : séquence inscription puis connexion identique pour une adresse prise et une adresse libre, et sept essais (dont le bon) sur un compte en attente qui répondent tous pareil (`21ab54d`). La page de connexion annonce qu'un compte demandé s'ouvre après sa validation. README, `docs/api.md`, backlog et parcours e2e sont mis à jour. |
| Majeur | S8.2 | Réactiver un compte rendait vie aux cookies coupés à sa désactivation : `get_current_user` ne contrôlait que le statut, et le jeton dure 10 h. Doublon : réinitialiser le mot de passe d'un compte compromis ne coupait aucune session. | Migration 0017 : colonne `sessions_valides_depuis`, datée par la désactivation et la réinitialisation. À la reprise, un compte déjà désactivé reçoit sa date de désactivation. Un jeton émis avant cette date (`iat`, comparé à la seconde) reçoit un 401. Le gérant qui change son propre mot de passe reçoit une nouvelle session. Tests : ancien cookie refusé après réactivation et après réinitialisation, nouvelle connexion acceptée, comparaison à la seconde, reprise de la migration (`477a25e`). |
| Majeur | S8.2 | Les OT en cours d'un mécanicien désactivé lui restaient affectés et n'étaient signalés nulle part. « Mécanicien à affecter » ne visait que les OT sans mécanicien. | Un OT non livré dont le mécanicien n'est plus actif remonte dans « À traiter maintenant » (« compte de Karim B. désactivé »). La règle pure `mecanicien_a_affecter` est testée. La fenêtre de désactivation d'un mécanicien l'annonce (`6354b05`). |
| Majeur | S1.5, S8.2 | Retour arrière : l'adresse gardait `?q=`, mais le champ était vide et la liste n'était pas filtrée, sur les six listes. Cause : Next.js réaffiche la page avec les paramètres de son premier rendu, et la liste lisait ces paramètres périmés. Même cause pour les Employés : le lien du menu ramenait sur `/employes` sans retirer le filtre de statut ou la recherche. | Hook `useFiltresAdresse` : chaque liste lit recherche, filtres et page dans `useSearchParams`, que Next.js synchronise avec `replaceState`, le retour arrière et les liens. Le champ de recherche reprend une recherche changée par une navigation, sans effacer une saisie en cours. Tests Vitest (retour arrière, lien du menu, saisie en cours) et Playwright (Clients, Ordres de travail, Employés : fiche ouverte puis retour arrière, puis lien du menu) (`99c790c`). |
| Mineur | S8.2 | Un compte repris sans nom de famille (« Admin », migration 0016) ne pouvait pas être modifié sans inventer un nom : 422 sur `nom`. | `PUT /utilisateurs/{id}` accepte un nom vide ; la création l'exige toujours. Le formulaire ne rend le nom facultatif que s'il est déjà vide (`7909bb1`). |
| Mineur | S1.5 | La liste des véhicules n'était pas rafraîchie après l'ajout ou la modification d'un véhicule, ni après la modification d'un client. | `rafraichirListesVehicules` invalide les listes des clients, des véhicules, des OT et des devis, ainsi que la recherche, dans les trois cas. Test Vitest sur la fiche véhicule (`4c8694e`). |
| Mineur | S1.5 | `?q=a` saisi dans l'adresse : l'API répondait 422, mais la liste annonçait « Aucun … ne correspond à « a ». » alors qu'aucune recherche n'avait eu lieu. | `texteDeRecherche` ignore une recherche de moins de 2 caractères, comme l'API : la liste s'affiche sans filtre. Tests Vitest (`99c790c`, même commit que le retour arrière : les deux touchent la lecture de l'adresse). |
| Mineur | S8.2 | Le focus retombait sur `<body>` après « Modifier », « Annuler » et la création d'un employé. | « Modifier » met le focus sur le premier champ. « Annuler » le rend à « Modifier ». À l'arrivée depuis « Nouvel employé », il va au titre de la fiche. Tests Vitest, et une vérification ajoutée au parcours e2e des comptes (`0c0415a`). |
| Mineur | Recette | Paul Girard (seed) affichait « Créé le » après sa dernière connexion et sa désactivation. | Le seed reconstruit une chronologie vraisemblable : arrivée et validation 400 jours avant la désactivation, dernière connexion 15 jours avant. Une base semée avant ce correctif est réparée au seed suivant. Test pytest (`ba70ca3`). |
| Mineur | Recette | Le parcours e2e des comptes laissait un mécanicien actif de plus à chaque exécution, et une demande en attente en cas d'échec. Ces demandes rapprochaient de la limite de 20. | `test.afterAll`, que le parcours réussisse ou non : désactive les comptes de recette créés par le fichier qui sont encore actifs, et refuse ceux qui attendent encore. Vérifié sur la base de dev : le nombre de mécaniciens actifs et de demandes en attente est le même avant et après la suite (`2a338ff`). Le `afterAll` est entré par erreur dans le commit du focus (`0c0415a`), dont le message ne le décrit pas. `2a338ff` le complète (réponse 204 du refus) et le documente. L'historique n'est pas réécrit. |

### Constats rejetés
Aucun : les constats décrivent des défauts réels. Deux points ont été traités autrement que
proposé :
- canal résiduel de la limite des demandes (S8.3) : avec 19 demandes en attente, inscrire une
  adresse puis une autre dit si la première était libre. Ce canal est documenté plutôt que
  supprimé (README, `services/inscription.py`). Compter aussi les doublons demanderait de garder
  une trace des adresses déjà connues. Le test coûte 19 demandes visibles dans « À traiter
  maintenant » et une place par adresse libre, et il ne marche qu'une fois : la file pleine
  bloque ensuite toute inscription ;
- blocage d'un compte actif par des essais d'inscription suivis de connexions (S8.3) : chaque
  401 sur un compte actif compte pour un échec, et 5 échecs le bloquent 15 minutes (423), ce qui
  révèle que l'adresse existe. Ce comportement vient de S8.1 et ne dépend pas de l'inscription :
  cinq mauvais mots de passe le produisent aussi. Il n'est pas modifié ici.

### Observé pendant la revue, non traité
- La comparaison de `sessions_valides_depuis` se fait à la seconde, la précision de `iat` dans
  le jeton : une session ouverte dans la même seconde qu'une désactivation reste acceptée. Ce cas
  est accepté et testé.

## Recette
Sur le build de production de l'interface (`docker-compose.demo.yml`), 18 tests Playwright :
les 13 de la version 1.0.0 (parcours gérant et mécanicien, accessibilité, mise en page), plus
le parcours des comptes (création d'un employé, connexion, désactivation, session refusée à la
navigation suivante, connexion refusée), l'inscription (confirmation neutre, connexion refusée
tant que le compte attend, validation comme mécanicien par Nadia, menu du mécanicien), la
recherche dans chaque liste et le retour arrière. La suite range ses comptes de test à la fin et
ne touche jamais aux comptes de démonstration.

Une course dans le test du retour arrière (lignes comptées avant l'arrivée de la liste filtrée)
a été trouvée à la vérification de clôture et corrigée (`fix/e2e-recherche-course`) : 18 sur 18.

## Démo
Segment de 2 minutes ajouté au [script de la démo](script-demo.md) : « Employés » (création,
désactivation), la demande d'Inès Morel validée depuis « Compte à valider », la recherche dans
les listes.

## Rétrospective
- **Bien** : les choix de sécurité de l'inscription ont été tranchés par le PO avant le
  développement (validation par un gérant), puis durcis par la revue (aucune énumération des
  comptes, sessions réellement coupées).
- **À améliorer** : l'implémentation a été interrompue deux fois (contrôle de sécurité de
  l'outil indisponible, puis limite d'usage). Le travail non commité a été repris, vérifié et
  découpé en commits par tâche ; des commits plus fréquents réduisent ce risque.
- **À améliorer** : un test de recette dépendait de la vitesse de la machine. Règle pour les
  tests Playwright : toujours attendre un signal de l'interface (annonce, ligne attendue) avant
  de compter ou de comparer.
- **Écart d'affinage** : voir le contexte ; la question est ajoutée à l'affinage.
