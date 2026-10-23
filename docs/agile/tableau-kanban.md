# Tableau de l'équipe

Le tableau vit dans OpenProject ; ce fichier en garde la configuration versionnée.

| Colonne | Entrée | Sortie | Limite WIP |
| --- | --- | --- | --- |
| Backlog produit | Story rédigée par le PO | Story estimée et priorisée | — |
| Prêt pour le sprint | Critères d'acceptation et tests listés | Choisie au sprint planning | — |
| En cours | Un binôme (dev + testeur) s'en charge | Code et tests écrits | **2 stories par personne** |
| En test | Tests automatisés verts | Recette du testeur réussie | 3 pour l'équipe |
| En revue | Recette réussie | Démontrée et acceptée par le PO | — |
| Terminé | DoD entièrement cochée | — | — |

## Règles
- Une story bloquée garde sa place et reçoit l'étiquette « Bloqué » ; le Scrum Master lève le blocage au daily.
- On ne tire une nouvelle story que si la limite WIP de la colonne le permet : on aide d'abord à terminer.
- Daily de 15 minutes ; revue et rétrospective à la fin de chaque sprint de 2 semaines.
- Les binômes tournent à chaque sprint pour répartir la charge entre développeurs et testeurs.
