# Modèle de données

Base PostgreSQL 16. Les montants sont des **entiers en centimes**, les dates des `timestamptz`
stockées en UTC et affichées en Europe/Paris. Chaque table a une clé `id` (entier auto-incrémenté)
et, sauf mention contraire, `cree_le` / `modifie_le`.

```mermaid
erDiagram
    UTILISATEUR ||--o{ ORDRE_TRAVAIL : "est affecté à"
    UTILISATEUR ||--o{ HISTORIQUE_STATUT : "effectue"
    UTILISATEUR |o--o{ UTILISATEUR : "valide ou désactive"
    CLIENT ||--o{ VEHICULE : "possède"
    VEHICULE ||--o{ RENDEZ_VOUS : "a"
    PONT ||--o{ RENDEZ_VOUS : "accueille"
    VEHICULE ||--o{ ORDRE_TRAVAIL : "fait l'objet de"
    RENDEZ_VOUS |o--o| ORDRE_TRAVAIL : "donne lieu à"
    ORDRE_TRAVAIL ||--o{ TACHE_OT : "comprend"
    ORDRE_TRAVAIL ||--o{ HISTORIQUE_STATUT : "trace"
    ORDRE_TRAVAIL ||--o{ DEVIS : "est chiffré par"
    DEVIS ||--|{ LIGNE_DEVIS : "contient"
    DEVIS ||--o| FACTURE : "est facturé par"
    FACTURE ||--|{ LIGNE_FACTURE : "fige"
    FACTURE ||--o{ PAIEMENT : "est réglée par"

    UTILISATEUR {
        int id PK
        citext email UK
        string prenom "obligatoire, 100 car."
        string nom "peut être vide (nom d'un seul mot repris en 0016)"
        string mot_de_passe_hash "argon2id"
        enum role "gerant | mecanicien"
        enum statut "statut_compte : actif | en_attente | desactive"
        int tentatives_echouees
        timestamptz bloque_jusqu_a "null si non bloqué"
        timestamptz derniere_connexion
        timestamptz valide_le "validation d'une inscription"
        int valide_par FK "gérant, SET NULL"
        timestamptz desactive_le "dernière désactivation"
        int desactive_par FK "gérant, SET NULL"
    }
    CLIENT {
        int id PK
        string nom "obligatoire"
        string prenom
        string telephone "obligatoire, normalisé 0XXXXXXXXX, indexé"
        citext email
        bool consentement_rappels "RGPD, faux par défaut"
        string adresse "facultative"
        string code_postal "5 chiffres, facultatif"
        string ville "facultative"
    }
    VEHICULE {
        int id PK
        int client_id FK
        string immatriculation UK "normalisée AA-123-AA"
        string marque
        string modele
        int kilometrage "≥ 0"
        string vin "17 caractères, facultatif"
        date date_mise_en_circulation "facultative"
    }
    PONT {
        int id PK
        string nom UK "Pont 1, Pont 2…"
        bool actif
    }
    RENDEZ_VOUS {
        int id PK
        int vehicule_id FK
        int pont_id FK
        timestamptz debut
        int duree_minutes "> 0"
        timestamptz fin "calculée"
        string motif
    }
    ORDRE_TRAVAIL {
        int id PK
        string numero UK "OT-AAAA-nnn"
        int vehicule_id FK "obligatoire"
        int rendez_vous_id FK "facultatif"
        int mecanicien_id FK "facultatif"
        text demande_client
        text diagnostic
        enum statut "a_faire | en_cours | termine | livre"
        bool prioritaire "affiché « Urgent »"
        int kilometrage_entree
        timestamptz restitution_prevue
        timestamptz ouvert_le
        timestamptz cloture_le
    }
    TACHE_OT {
        int id PK
        int ordre_travail_id FK
        string libelle
        int duree_prevue_minutes
        int position
        bool terminee
        timestamptz terminee_le
        int terminee_par FK
    }
    HISTORIQUE_STATUT {
        int id PK
        int ordre_travail_id FK
        enum ancien "null à la création"
        enum nouveau
        timestamptz change_le
        int utilisateur_id FK
    }
    COMPTEUR {
        string type PK "OT | FACTURE"
        int annee PK
        int dernier
    }
    DEVIS {
        int id PK
        int ordre_travail_id FK
        enum statut "brouillon | envoye | accepte | refuse"
        timestamptz envoye_le "null tant que brouillon"
        timestamptz decide_le "acceptation ou refus"
        int decide_par FK "auteur de la décision"
        int taux_tva_bp "2000 = 20 %"
        int total_ht_centimes
        int total_tva_centimes
        int total_ttc_centimes
    }
    LIGNE_DEVIS {
        int id PK
        int devis_id FK
        enum type "piece | main_oeuvre"
        string reference
        string designation
        numeric quantite "> 0, 2 décimales"
        int prix_unitaire_ht_centimes "≥ 0"
        int total_ht_centimes
        int position
    }
    FACTURE {
        int id PK
        string numero UK "F-AAAA-nnn, sans trou"
        int devis_id FK,UK
        timestamptz emise_le
        date echeance
        date date_prestation "fin de la prestation (Paris), null avant la migration 0015"
        jsonb client_fige "adresse comprise depuis la migration 0015"
        jsonb vehicule_fige
        int total_ht_centimes
        int total_tva_centimes
        int total_ttc_centimes
    }
    LIGNE_FACTURE {
        int id PK
        int facture_id FK
        enum type
        string reference
        string designation
        numeric quantite
        int prix_unitaire_ht_centimes
        int total_ht_centimes
    }
    PAIEMENT {
        int id PK
        int facture_id FK
        int montant_centimes "> 0, cumul ≤ TTC"
        enum mode "carte | especes | cheque | virement"
        timestamptz recu_le
        string reference "n° de chèque ou de virement, facultatif"
        int cree_par FK
        timestamptz cree_le
    }
```

## Règles portées par la base

| Règle | Mécanisme |
| --- | --- |
| E-mail utilisateur unique, sans tenir compte de la casse | `citext` + contrainte unique |
| Immatriculation unique | normalisation applicative (majuscules, tirets) + contrainte unique |
| Pas deux rendez-vous qui se chevauchent sur un même pont | `EXCLUDE USING gist (pont_id WITH =, tstzrange(debut, fin) WITH &&)` |
| Numéros d'OT et de facture continus, sans trou | table `compteur` verrouillée (`SELECT … FOR UPDATE`) dans la transaction d'insertion |
| Facture non modifiable | trigger `BEFORE UPDATE OR DELETE` qui lève une exception |
| Quantité > 0, prix ≥ 0, kilométrage ≥ 0, durée > 0 | contraintes `CHECK` |
| Un devis facturé au plus une fois | `facture.devis_id` unique |
| Au plus un devis non refusé par OT | index unique partiel `uq_devis_ordre_non_refuse` (`WHERE statut <> 'refuse'`) |
| Statut du devis cohérent avec ses dates | `CHECK statut_coherent` (brouillon sans envoi, envoyé daté, décision datée) |
| Cumul des paiements d'une facture ≤ son TTC | trigger `paiement_plafond` (BEFORE INSERT) qui verrouille la facture (`SELECT … FOR UPDATE`) puis refuse le dépassement (SQLSTATE `ET002`) |
| Paiement non modifiable | trigger `BEFORE UPDATE OR DELETE` et `BEFORE TRUNCATE` (SQLSTATE `ET003`) ; aucune donnée de carte n'est enregistrée (« carte » = terminal du garage) |
| Recherche sans accents ni casse, par morceau de nom, de téléphone ou de plaque | extension `unaccent`, fonction IMMUTABLE `etabli_normaliser`, index GIN `pg_trgm` (nom + prénom, téléphone, plaque sans tirets) |

## Statuts de l'ordre de travail

Transitions autorisées, une étape à la fois, sans retour :

```mermaid
stateDiagram-v2
    [*] --> a_faire
    a_faire --> en_cours
    en_cours --> termine
    termine --> livre
    livre --> [*]
```

Correspondance avec les badges du design system : `a_faire` → « En attente » (anneau),
`en_cours` → « En cours », `termine` → « Prêt », `livre` → « Livré ». `prioritaire = true` ajoute le
badge « Urgent » (losange) et la bande jaune `signal` sur la carte.

## Statut d'un compte

Stories S8.2 et S8.3, migration 0016. `statut` (type `statut_compte`) remplace le booléen
`actif` : une seule colonne fait foi (le modèle garde une propriété `actif` en lecture, vraie
pour le statut `actif`), et seul un compte actif ouvre une session, vérifié à chaque requête.
La migration a repris le prénom du nom existant, coupé au premier espace (« Nadia Benali » →
« Nadia » + « Benali », « Karim B. » → « Karim » + « B. ») : le nom affiché, prénom puis nom,
est inchangé. Le downgrade recolle prénom et nom et rend `actif = (statut = 'actif')`.

```mermaid
stateDiagram-v2
    [*] --> actif : créé par un gérant, ou premier compte du garage
    [*] --> en_attente : inscription (POST /auth/register)
    en_attente --> actif : validé par un gérant (rôle choisi, valide_le, valide_par)
    en_attente --> [*] : refusé par un gérant (demande supprimée)
    actif --> desactive : désactivé par un gérant (desactive_le, desactive_par)
    desactive --> actif : réactivé par un gérant
```

Badges : `actif` → « Actif » (`pret`), `en_attente` → « En attente de validation »
(`en-cours`), `desactive` → « Désactivé » (`livre`) ; un compte bloqué après 5 échecs porte en plus
« Bloqué jusqu'à 15 h 02 » (`urgent`). Il reste toujours au moins un gérant actif : l'API verrouille les
lignes des gérants actifs (`SELECT … FOR UPDATE`) avant de les compter.

## Statuts du devis

Story S4.2. Seul un brouillon se modifie ; seul un devis accepté se facture ; un devis refusé
peut être remplacé par un nouveau devis sur le même OT.

```mermaid
stateDiagram-v2
    [*] --> brouillon
    brouillon --> envoye : marqué envoyé au client
    envoye --> accepte : accepté par le client
    envoye --> refuse : refusé par le client
    accepte --> [*] : facturé
    refuse --> [*]
```

Badges : `brouillon` → « Brouillon » (anneau, `attente`), `envoye` → « Envoyé » (`en-cours`),
`accepte` → « Accepté » (`pret`), `refuse` → « Refusé » (`urgent`, couleur `danger`).
