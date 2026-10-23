# Établi — design system

Établi est le système visuel d'une application de gestion de garage automobile : planning d'atelier, ordres de réparation (OR), fiches véhicules et clients, devis, factures, stock de pièces. Il est pensé pour deux postes à la fois : l'accueil (desktop, souris, clients au comptoir) et l'atelier (tablette accrochée près du pont, lue à un mètre, touchée avec des gants). Ceci est une première proposition, sans marque existante : logo, couleurs et polices sont à valider.

## Principes

- **Lisible à un mètre.** Texte courant à 15 px minimum, chiffres en condensé gras, contrastes ≥ 4.5:1 dans les deux thèmes. Si un mécanicien doit se pencher pour lire un statut, c'est raté.
- **Le statut d'abord.** Chaque véhicule a un statut d'intervention visible partout (planning, liste, fiche) avec la même couleur, la même pastille, le même mot.
- **Des données qu'on recopie.** Immatriculation, VIN, références pièces et kilométrage sont en mono (`data`) : on les compare caractère par caractère.
- **Sobre comme un outil.** Fonds béton, filets plutôt qu'ombres, une seule couleur d'action (`petrol`). Le jaune `signal` est le marquage au sol : rare, donc remarqué.

## Voix

On parle comme un chef d'atelier à un client : clair, concret, sans jargon inutile.

- Faire : « Plaquettes avant à remplacer — 148,00 € TTC », « Prêt à 17 h 30 », « Pièce commandée, livraison jeudi ».
- Éviter : points d'exclamation, majuscules partout, abréviations internes devant le client (« OR » est réservé à l'atelier ; au client on dit « intervention »).
- Montants toujours TTC avec la virgule française et l'espace insécable avant € ; heures au format « 17 h 30 » ; dates « mar. 14 oct. ».

## Couleurs

- **Surfaces** : `surface` (page), `surface-raised` (cartes, champs), `surface-sunken` (en-têtes de tableau, colonnes du planning). Texte en `ink`, secondaire en `ink-muted`.
- **Navigation** : barre latérale en `graphite`, texte `on-graphite`.
- **Action** : `petrol` (bouton principal, liens, progression) avec `on-petrol` pour le texte posé dessus ; `petrol-soft` pour une ligne sélectionnée. Un seul bouton principal par vue.
- **Accent** : `signal`, réservé aux priorités (client qui attend sur place, véhicule de remplacement à rendre). Jamais en texte sur une surface.
- **Focus** : l'ombre `focus-ring` sur tout élément interactif, jamais retirée.

### Statuts d'intervention

Toujours un badge `StatusBadge` : pastille + mot, jamais la couleur seule. Les pastilles diffèrent aussi par la forme (pleine, anneau, losange) pour rester distinctes sans la couleur.

| Statut | Clé | Couleurs | Pastille |
| --- | --- | --- | --- |
| En attente | `attente` | `ink-muted` sur `surface-sunken` | anneau |
| Diagnostic | `diagnostic` | `info` sur `info-soft` | pleine |
| En cours | `en-cours` | `warning` sur `warning-soft` | pleine |
| Attente pièces | `pieces` | `parts` sur `parts-soft` | anneau |
| Prêt | `pret` | `success` sur `success-soft` | pleine |
| Livré | `livre` | `ink-muted`, contour `line` | anneau |
| Urgent | `urgent` | `danger` sur `danger-soft` | losange |

## Typographie

Trois familles Google Fonts (chargées par `components/bundle.css`) :

- **Barlow Semi Condensed** (`condensed`) pour les titres et les chiffres clés : une allure de signalétique routière, compacte sur les cartes du planning.
- **Barlow** (`sans`) pour le texte et les formulaires.
- **JetBrains Mono** (`mono`) pour VIN, immatriculations hors plaque, références, kilométrage, numéros d'OR.

Échelle : `display` 40, `h1` 28, `h2` 22, `h3` 18, `body` 15, `caption` 13, `label` 12 en capitales, `data` 14 mono, `kpi` 32. Les chiffres des tableaux et KPI utilisent `font-variant-numeric: tabular-nums`.

## Espacement, rayons, élévation

- Grille de 4 px (`space-1` à `space-7`). Cibles tactiles ≥ 44 px : boutons `md` à 44 px, `sm` (36 px) réservé au desktop.
- Rayons nets : `radius-sm` 4 (badges, plaque), `radius-md` 6 (boutons, champs, cartes), `radius-lg` 10 (panneaux, tuiles).
- Ombres discrètes : `shadow-card` seulement pour une carte sur la page, `shadow-overlay` pour ce qui flotte. Le reste se structure par filets `line`.

## Iconographie

Aucun jeu d'icônes n'est fourni pour l'instant. Recommandation : une famille au trait de 1,5 px, angles légèrement arrondis, 20 px dans les boutons et 24 px dans la navigation, couleur `ink` ou `on-graphite`. Une icône accompagne toujours un libellé, sauf actions universelles (fermer, rechercher). Pas de pictogrammes de voitures illustrées : le véhicule se montre par sa plaque (`Plate`) et son modèle.

## Logo

Pas de logo à ce stade : le nom « Établi » s'écrit en Barlow Semi Condensed 600, couleur `ink` (ou `on-graphite` dans la barre latérale).

## Composants

`window.Etabli` (React 18) : `Button`, `StatusBadge`, `Plate`, `TextField`, `KpiTile`, `WorkOrderCard`. Classes CSS préfixées `et-` dans `components/bundle.css`.
