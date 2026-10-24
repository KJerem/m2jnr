# Sprint 1 — Accès et fiches

**Dates** : 2 au 13 novembre 2026 · **Engagé** : 9 points · **Livré** : 9 points · **Tag** : `sprint-1`

## Objectif
Un employé se connecte avec son rôle ; le gérant enregistre un client et son véhicule.

## Stories livrées
| Story | Pts | Branche | Résultat |
| --- | --- | --- | --- |
| S8.1 Connexion et rôles | 5 | `feature/S8.1-connexion-roles` | argon2id, blocage 15 min après 5 échecs, session httpOnly, CSRF, 403 par rôle, seed |
| S1.1 Fiche client | 2 | `feature/S1.1-fiche-client` | création, modification, liste paginée, téléphone normalisé, alerte de doublon |
| S1.2 Fiche véhicule | 2 | `feature/S1.2-fiche-vehicule` | immatriculation SIV unique, kilométrage validé, fiche lisible par le mécanicien |

## Definition of Done
- [x] Un commit par tâche du backlog, branches fusionnées en `--no-ff`
- [x] API : 125 tests pytest, ruff, mypy strict — verts
- [x] Web : 38 tests Vitest, ESLint, TypeScript, build — verts
- [x] Règles d'accès testées (mécanicien : 403 sur clients, devis, factures)
- [x] Vérification dans le navigateur à 1024 px (Playwright), thèmes clair et sombre
- [x] CHANGELOG à jour

## Revue de code
Deux relecteurs indépendants (back/sécurité et front/design) ont remonté 10 constats, tous confirmés
et corrigés sur `fix/sprint-1-revue`, chacun avec un test qui échouait avant la correction :

| Gravité | Constat |
| --- | --- |
| Majeur | Un compte désactivé pouvait être bloqué et répondait 423 au lieu de 401 |
| Majeur | La transaction était validée après l'envoi de la réponse HTTP (portée des dépendances FastAPI) |
| Majeur | La fenêtre de doublon ne rendait pas le focus au bouton d'origine |
| Majeur | La déconnexion provoquait un appel `/auth/me` en 401 et un rechargement complet |
| Mineur | Chiffres non ASCII acceptés puis erreur 500 en base (téléphone, plaque) |
| Mineur | Identifiants hors limites : 500 au lieu de 404 |
| Mineur | Contraintes CHECK avec un double préfixe (migration 0005) |
| Mineur | Le seed ne débloquait pas un compte de démonstration |
| Mineur | Le proxy n'excluait pas tout `/_next` |
| Mineur | Cibles tactiles de 36 px au lieu de 44 px |

## Démo
1. http://localhost:3000 sans session → redirection vers `/connexion`.
2. `nadia@garage.test` (gérant) : liste des 8 clients de démonstration, création d'un client avec un
   téléphone déjà connu → alerte de doublon, ajout d'un véhicule `gh482kl` → refusé (déjà enregistré).
3. `karim@garage.test` (mécanicien) : menu réduit, `/clients` → page 403, fiche véhicule lisible
   sans téléphone ni e-mail du propriétaire.
4. Cinq mauvais mots de passe sur un compte de test → « Compte bloqué jusqu'à … ».

## Rétrospective
- **Bien** : les règles métier sont dans des services purs, testés sans HTTP ; la revue croisée a
  trouvé de vrais défauts (transaction, focus) que les tests ne couvraient pas.
- **À améliorer** : le serveur de développement web ne voyait pas toujours les fichiers modifiés
  (redémarrage nécessaire). Action : vérifier le rechargement à chaud au début du sprint 2.
- **Décision technique** : toutes les routes utilisent l'alias `DbSession` (session validée avant la réponse).
