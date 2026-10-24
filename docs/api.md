# API d'Établi

La référence complète (schémas, paramètres, exemples) est générée par FastAPI :
**http://localhost:8000/docs** (OpenAPI, environnement de développement). Ce document en donne
la carte, par ressource, avec le rôle exigé et les principaux codes d'erreur. Le navigateur
appelle ces routes sous le préfixe `/api` (réécriture de Next.js vers l'API).

## Conventions

- **Session** : cookie httpOnly posé par `POST /auth/login` ; sans session valide, toute route
  autre que `/health`, `/auth/csrf` et `/auth/login` répond **401** `non_authentifie`.
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

## Connexion et santé

| Méthode et route | Rôle | Rôle de la route | Erreurs principales |
| --- | --- | --- | --- |
| `GET /health` | public | état de l'API et de la base | — |
| `GET /auth/csrf` | public | jeton CSRF (crée le cookie) | — |
| `POST /auth/login` | public | connexion `{email, mot_de_passe}` | 401 `identifiants_invalides`, 423 `compte_bloque` (heure de déblocage) |
| `POST /auth/logout` | connecté | déconnexion | — |
| `GET /auth/me` | connecté | utilisateur courant | 401 |

## Clients et véhicules

| Méthode et route | Rôle | Rôle de la route | Erreurs principales |
| --- | --- | --- | --- |
| `GET /clients?page&taille` | gérant | liste paginée | — |
| `POST /clients?confirmer_doublon=` | gérant | création (adresse facultative) | 422, 409 `doublon_telephone` (confirmable par `?confirmer_doublon=true`) |
| `GET /clients/{id}` | gérant | fiche et véhicules | 404 |
| `PUT /clients/{id}?confirmer_doublon=` | gérant | modification complète | 422, 409 `doublon_telephone` |
| `GET /clients/{id}/vehicules` | gérant | véhicules du client | 404 |
| `POST /clients/{id}/vehicules` | gérant | rattacher un véhicule | 422, 409 `immatriculation_existante` |
| `GET /vehicules` | gérant, mécanicien | véhicules | — |
| `GET /vehicules/{id}` | gérant, mécanicien | fiche véhicule | 404 |
| `PUT /vehicules/{id}` | gérant | modification | 422, 409 `immatriculation_existante` |
| `GET /vehicules/{id}/historique` | gérant, mécanicien | interventions, de la plus récente à la plus ancienne | 404 |

## Atelier

| Méthode et route | Rôle | Rôle de la route | Erreurs principales |
| --- | --- | --- | --- |
| `GET /ordres?statut&mecanicien_id&vehicule_id&du&au&atelier&page&taille` | gérant, mécanicien | liste filtrée | 422 |
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
| `GET /devis?page&taille` | liste | — |
| `GET /devis/{id}` | détail | 404 |
| `PUT /devis/{id}` | remplacement des lignes (brouillon seulement) | 409 `devis_verrouille`, `devis_facture` |
| `POST /devis/{id}/statut` | `{nouveau}` : brouillon → envoye → accepte ou refuse | 409 `transition_devis_interdite` |
| `POST /devis/{id}/facture` | émission `F-AAAA-nnn` | 409, dans cet ordre : `devis_deja_facture`, `devis_non_accepte`, `devis_vide`, `ordre_non_termine` |
| `GET /factures?du&au&statut_paiement&page&taille` | liste (statut de paiement `impayee`, `partielle`, `payee`) | 422 |
| `GET /factures/{id}` | facture figée, paiements, déjà payé, reste, statut, retard, date de prestation | 404 |
| `GET /factures/{id}/pdf` | PDF (`application/pdf`, identique à chaque téléchargement) | 404 |
| `POST /factures/{id}/paiements` | `{montant_centimes, mode, recu_le?, reference?}` → 201 facture à jour | 404, puis 409 `facture_payee`, 422 `recu_le` (futur ou avant l'émission), 409 `trop_percu` (avec `reste_centimes`) |

## Recherche et tableau de bord (gérant seul)

| Méthode et route | Rôle de la route | Erreurs principales |
| --- | --- | --- |
| `GET /recherche?q` | clients, véhicules, OT, factures (20 au plus par rubrique) par nom sans accents, téléphone, plaque, numéro d'OT ou de facture | 422 « Saisissez au moins 2 caractères. » |
| `GET /tableau-de-bord` | indicateurs, interventions du jour, arrivées, « À traiter maintenant » (`retard`, `devis_a_valider`, `facture_a_etablir`, `non_affecte`) | — |

## Codes propres à la base

Quand une écriture contourne l'API, la base refuse elle-même (SQLSTATE) : `ET001` facture ou
ligne de facture modifiée, supprimée ou ajoutée après l'émission ; `ET002` paiement qui ferait
dépasser le TTC ; `ET003` paiement modifié ou supprimé. L'API traduit `ET002` en 409
`trop_percu`.
