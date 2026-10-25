# API d'Établi

La référence complète (schémas, paramètres, exemples) est générée par FastAPI :
**http://localhost:8000/docs** (OpenAPI, environnement de développement). Ce document en donne
la carte, par ressource, avec le rôle exigé et les principaux codes d'erreur. Le navigateur
appelle ces routes sous le préfixe `/api` (réécriture de Next.js vers l'API).

## Conventions

- **Session** : cookie httpOnly posé par `POST /auth/login` (ou par `POST /auth/register` pour
  le premier compte du garage) ; sans session valide, toute route autre que `/health`,
  `/auth/csrf`, `/auth/login`, `/auth/inscription` et `/auth/register` répond **401**
  `non_authentifie`. Le compte est relu à chaque requête : une session d'un compte désactivé
  depuis répond 401 dès la requête suivante.
- **CSRF** : toute requête POST, PUT, PATCH ou DELETE porte l'en-tête `X-CSRF-Token`, égal au
  cookie `csrf_token` obtenu par `GET /auth/csrf` ; sinon **403** `csrf_invalide`.
- **Rôles** : `gerant` ou `mecanicien` ; un rôle non autorisé reçoit **403** `interdit`. Le
  mécanicien ne reçoit jamais de montant, ni le téléphone, l'e-mail ou l'adresse d'un client.
- **Erreurs** : toujours `{"code", "message", "champs", …détails}`. `message` est en français
  et s'affiche tel quel ; `champs` associe un champ à son erreur (**422** `validation`) ; un
  409 peut ajouter des détails (`reste_centimes`, `numero`, `clients`…). Identifiant inconnu
  ou hors limites : **404** `introuvable`.
- **Formats** : montants en centimes (entiers) ; quantités de devis en texte (« 1,5 ») ; dates
  et heures en ISO 8601 avec décalage horaire (`Z`, `+01:00` ou `+02:00` selon la valeur :
  un même instant peut s'écrire de plusieurs façons, à lire et comparer comme un instant) ;
  une date et heure sans fuseau envoyée par l'interface est lue à l'heure de Paris ; jours
  `AAAA-MM-JJ` entre 2000 et 2100 ; listes paginées `{elements, total, page, taille}`.
- **Recherche dans les listes** (stories S8.2 et S1.5) : `GET /clients`, `/vehicules`,
  `/ordres`, `/devis`, `/factures` et `/utilisateurs` acceptent `q` (2 à 100 caractères après
  suppression des espaces de bord, sinon **422** sur `q` : « Saisissez au moins 2
  caractères. », « 100 caractères au plus. », « Caractère non autorisé. ») ; `q` absent ou vide
  ne filtre pas. Chaque mot est cherché sans accents ni casse, « % » et « _ » pris à la lettre ;
  le filtre s'applique dans la requête paginée (le `total` compte les résultats). Le
  mécanicien ne cherche jamais par le téléphone ou l'e-mail d'un client.

## Connexion et santé

| Méthode et route | Rôle | Rôle de la route | Erreurs principales |
| --- | --- | --- | --- |
| `GET /health` | public | état de l'API et de la base | — |
| `GET /auth/csrf` | public | jeton CSRF (crée le cookie) | — |
| `POST /auth/login` | public | connexion `{email, mot_de_passe}` | 401 `identifiants_invalides` (e-mail inconnu, mauvais mot de passe, compte désactivé ou compte en attente de validation, même avec le bon mot de passe), 423 `compte_bloque` (heure de déblocage) |
| `GET /auth/inscription` | public | `{premier_compte}` : la prochaine inscription crée-t-elle le premier compte du garage ? | — |
| `POST /auth/register` | public (CSRF exigé) | inscription `{prenom, nom, email, mot_de_passe}` : **201** `{compte_actif: true, utilisateur}` et session pour le premier compte (aucun gérant actif) ; sinon **202** `{compte_actif: false, message}` « Demande enregistrée. Un gérant du garage doit valider votre compte avant votre première connexion. », identique pour un e-mail déjà connu (rien n'est créé ni modifié) | 422 (mot de passe de moins de 12 caractères, e-mail invalide), 429 `trop_de_demandes` (20 demandes en attente, `MAX_COMPTES_EN_ATTENTE`) |
| `POST /auth/logout` | connecté | déconnexion | — |
| `GET /auth/me` | connecté | utilisateur courant (`prenom`, `nom`, `nom_affiche`, `role`) | 401 |

## Employés (gérant seul)

Stories S8.2 et S8.3. Le mécanicien reçoit **403** `interdit` sur chacune de ces routes. Une
sortie `UtilisateurSortie` vaut `{id, prenom, nom, nom_affiche, email, role, statut,
bloque_jusqu_a, derniere_connexion, cree_le, valide_le, desactive_le}` (`statut` : `actif`,
`en_attente` ou `desactive`) ; le hash du mot de passe n'est jamais renvoyé.

| Méthode et route | Rôle de la route | Erreurs principales |
| --- | --- | --- |
| `GET /utilisateurs?q&role&statut&page&taille` | liste (recherche sur prénom, nom, e-mail ; en attente, puis actifs, puis désactivés, puis par nom) | 422 |
| `POST /utilisateurs` | création `{prenom, nom, email, mot_de_passe, role}` → 201, compte actif | 422 (mot de passe de moins de 12 caractères), 409 `email_existant` (sans tenir compte de la casse) |
| `GET /utilisateurs/{id}` | fiche | 404 |
| `PUT /utilisateurs/{id}` | modification `{prenom, nom, email, role}` | 409 `email_existant`, `soi_meme` (changer son propre rôle), `dernier_gerant` « Il doit rester au moins un gérant actif. » |
| `POST /utilisateurs/{id}/mot-de-passe` | réinitialisation `{mot_de_passe}` (12 caractères au moins), débloque aussi le compte | 404, 422 |
| `POST /utilisateurs/{id}/debloquer` | remet à zéro les échecs et le blocage | 404 |
| `POST /utilisateurs/{id}/desactiver` | actif → désactivé (date et auteur gardés) ; ses sessions s'arrêtent | 409 `soi_meme`, `dernier_gerant`, `statut_incompatible` |
| `POST /utilisateurs/{id}/reactiver` | désactivé → actif | 409 `statut_incompatible` |
| `POST /utilisateurs/{id}/valider` | inscription en attente → actif, `{role}` choisi par le gérant (date et auteur gardés) | 409 `statut_incompatible` (le compte n'attend pas de validation) |
| `POST /utilisateurs/{id}/refuser` | refus d'une inscription en attente : la demande est supprimée → 204 | 409 `statut_incompatible` |

Les lignes des gérants actifs sont verrouillées (`SELECT … FOR UPDATE`) avant d'être comptées :
deux rétrogradations ou désactivations simultanées ne laissent jamais le garage sans gérant
actif.

## Clients et véhicules

| Méthode et route | Rôle | Rôle de la route | Erreurs principales |
| --- | --- | --- | --- |
| `GET /clients?q&page&taille` | gérant | liste paginée ; `q` : nom, prénom, téléphone même partiel, plaque d'un véhicule (avec ou sans tirets), e-mail (saisie avec « @ » ou « . ») | 422 |
| `POST /clients?confirmer_doublon=` | gérant | création (adresse facultative) | 422, 409 `doublon_telephone` (confirmable par `?confirmer_doublon=true`) |
| `GET /clients/{id}` | gérant | fiche et véhicules | 404 |
| `PUT /clients/{id}?confirmer_doublon=` | gérant | modification complète | 422, 409 `doublon_telephone` |
| `GET /clients/{id}/vehicules` | gérant | véhicules du client | 404 |
| `POST /clients/{id}/vehicules` | gérant | rattacher un véhicule | 422, 409 `immatriculation_existante` |
| `GET /vehicules?q&page&taille` | gérant, mécanicien | liste paginée groupée par propriétaire (`taille` jusqu'à 1 000 pour les listes de choix) ; `q` : plaque avec ou sans tirets, marque, modèle, VIN, nom du propriétaire (jamais ses coordonnées) | 422 |
| `GET /vehicules/{id}` | gérant, mécanicien | fiche véhicule | 404 |
| `PUT /vehicules/{id}` | gérant | modification | 422, 409 `immatriculation_existante` |
| `GET /vehicules/{id}/historique` | gérant, mécanicien | interventions, de la plus récente à la plus ancienne | 404 |

## Atelier

| Méthode et route | Rôle | Rôle de la route | Erreurs principales |
| --- | --- | --- | --- |
| `GET /ordres?statut&mecanicien_id&vehicule_id&du&au&atelier&q&page&taille` | gérant, mécanicien | liste filtrée ; `q` : numéro, plaque, marque, modèle, client, mécanicien, demande | 422 |
| `POST /ordres` | gérant | ouverture, numéro `OT-AAAA-nnn` | 422 (véhicule obligatoire) |
| `GET /ordres/{id}` | gérant, mécanicien | fiche, tâches, suivi (coordonnées du client au gérant seul) | 404 |
| `PUT /ordres/{id}` | gérant | modification (tâches comprises) | 409 `ordre_livre`, `ordre_pret` |
| `POST /ordres/{id}/statut` | gérant, mécanicien | `{nouveau}` : une étape, sans retour | 409 `transition_interdite`, `taches_non_terminees` |
| `POST /ordres/{id}/taches/{tache_id}/terminer` | gérant, mécanicien | cocher une tâche | 404, 409 `ordre_livre` |
| `POST /ordres/{id}/taches/{tache_id}/rouvrir` | gérant, mécanicien | décocher une tâche | 404, 409 `ordre_livre`, `ordre_pret` |
| `GET /mecaniciens` | gérant, mécanicien | mécaniciens actifs | — |
| `GET /ponts` | gérant, mécanicien | ponts de l'atelier | — |
| `GET /planning?jour` | gérant, mécanicien | planning du jour par pont, « À planifier » | 422 |
| `GET /rendez-vous?du&au&pont_id` | gérant, mécanicien | rendez-vous à venir | 422 |
| `POST /rendez-vous` | gérant | prise de rendez-vous | 422 (date passée), 409 `creneau_occupe` |
| `POST /rendez-vous/{id}/ordre` | gérant | ouvrir l'OT du rendez-vous | 409 `ordre_existant` |

## Devis, factures et paiements (gérant seul)

| Méthode et route | Rôle de la route | Erreurs principales |
| --- | --- | --- |
| `POST /ordres/{id}/devis` | création (lignes, totaux calculés) | 422 (quantité ≤ 0, aucune ligne), 409 `devis_existant` (un devis non refusé existe déjà) |
| `GET /ordres/{id}/devis` | devis courant : le non refusé, à défaut le dernier refusé | 404 |
| `GET /devis?q&page&taille` | liste ; `q` : numéro d'OT, plaque, client | 422 |
| `GET /devis/{id}` | détail | 404 |
| `PUT /devis/{id}` | remplacement des lignes (brouillon seulement) | 409 `devis_verrouille`, `devis_facture` |
| `POST /devis/{id}/statut` | `{nouveau}` : brouillon → envoye → accepte ou refuse | 409 `transition_devis_interdite` |
| `POST /devis/{id}/facture` | émission `F-AAAA-nnn` | 409, dans cet ordre : `devis_deja_facture`, `devis_non_accepte`, `devis_vide`, `ordre_non_termine` |
| `GET /factures?du&au&statut_paiement&q&page&taille` | liste (statut de paiement `impayee`, `partielle`, `payee`) ; `q` : numéro de facture ou d'OT, client et plaque de la copie figée | 422 |
| `GET /factures/{id}` | facture figée, paiements, déjà payé, reste, statut, retard, date de prestation | 404 |
| `GET /factures/{id}/pdf` | PDF (`application/pdf`, identique à chaque téléchargement) | 404 |
| `POST /factures/{id}/paiements` | `{montant_centimes, mode, recu_le?, reference?}` → 201 facture à jour | 404, puis 409 `facture_payee`, 422 `recu_le` (futur ou avant l'émission), 409 `trop_percu` (avec `reste_centimes`) |

## Recherche et tableau de bord (gérant seul)

| Méthode et route | Rôle de la route | Erreurs principales |
| --- | --- | --- |
| `GET /recherche?q` | clients, véhicules, OT, factures (20 au plus par rubrique) par nom sans accents, téléphone, plaque, numéro d'OT ou de facture | 422 « Saisissez au moins 2 caractères. » |
| `GET /tableau-de-bord` | indicateurs, interventions du jour, arrivées, « À traiter maintenant » (`retard`, `devis_a_valider`, `facture_a_etablir`, `non_affecte`, `compte_a_valider` avec `utilisateur_id`) | — |

## Codes propres à la base

Quand une écriture contourne l'API, la base refuse elle-même (SQLSTATE) : `ET001` facture ou
ligne de facture modifiée, supprimée ou ajoutée après l'émission ; `ET002` paiement qui ferait
dépasser le TTC ; `ET003` paiement modifié ou supprimé. L'API traduit `ET002` en 409
`trop_percu`.
