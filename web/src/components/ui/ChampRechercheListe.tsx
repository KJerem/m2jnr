"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Icon } from "./Icon";

export const DELAI_RECHERCHE_MS = 300;
export const LONGUEUR_MIN_RECHERCHE = 2;
export const LONGUEUR_MAX_RECHERCHE = 100;
export const MESSAGE_RECHERCHE_COURTE = "Saisissez au moins 2 caractères.";

/** « 1 résultat », « 3 résultats », « Aucun résultat ». */
export function annonceResultats(total: number): string {
  if (total === 0) return "Aucun résultat";
  return `${total} résultat${total > 1 ? "s" : ""}`;
}

export interface ChampRechercheListeProps {
  /** Étiquette visible du champ, par exemple « Rechercher un client ». */
  libelle: string;
  placeholder?: string;
  /** Saisie de départ (paramètre ?q= de l'adresse). */
  valeurInitiale?: string;
  /**
   * Recherche à appliquer, sans espaces de bord ; « » quand le champ est effacé. Appelée
   * 300 ms après la dernière frappe, tout de suite avec Entrée ou « Effacer ». Une saisie
   * d'un seul caractère n'est pas envoyée (l'API demande 2 caractères au moins).
   */
  onRecherche: (q: string) => void;
  /** Nombre de résultats de la recherche en cours (annoncé poliment), ou null s'il n'y en a pas. */
  total?: number | null;
  /** Erreur renvoyée par l'API (422 sur « q »). */
  erreurServeur?: string | null;
  className?: string;
}

/**
 * Champ de recherche d'une liste (stories S8.2 et S1.5) : role="search", étiquette visible,
 * recherche lancée pendant la frappe (délai de 300 ms) ou avec Entrée, bouton « Effacer »
 * qui rend le focus au champ, nombre de résultats annoncé (aria-live polite). La liste qui
 * l'emploie garde la saisie dans l'adresse (?q=) et repart de la page 1.
 */
export function ChampRechercheListe({ libelle, placeholder, valeurInitiale = "", onRecherche, total = null, erreurServeur = null, className }: ChampRechercheListeProps) {
  const id = useId();
  const champ = useRef<HTMLInputElement>(null);
  const minuteur = useRef<number | undefined>(undefined);
  // Dernier rappel reçu : le minuteur appelle toujours la version à jour (filtres courants).
  const rappel = useRef(onRecherche);
  // Dernière recherche transmise à la liste (pas de second appel pour la même saisie).
  const transmise = useRef(valeurInitiale.trim());
  const [valeur, setValeur] = useState(valeurInitiale);
  const [erreur, setErreur] = useState<string | null>(null);
  const [recherche, setRecherche] = useState(valeurInitiale.trim());
  const message = erreur ?? erreurServeur;

  useEffect(() => {
    rappel.current = onRecherche;
  });
  useEffect(() => () => window.clearTimeout(minuteur.current), []);

  function appliquer(saisie: string, immediat: boolean) {
    window.clearTimeout(minuteur.current);
    const texte = saisie.trim();
    if (texte.length > 0 && texte.length < LONGUEUR_MIN_RECHERCHE) {
      if (immediat) setErreur(MESSAGE_RECHERCHE_COURTE);
      return;
    }
    setErreur(null);
    if (texte === transmise.current) return;
    transmise.current = texte;
    setRecherche(texte);
    rappel.current(texte);
  }

  function saisir(texte: string) {
    setValeur(texte);
    if (erreur) setErreur(null);
    window.clearTimeout(minuteur.current);
    minuteur.current = window.setTimeout(() => appliquer(texte, false), DELAI_RECHERCHE_MS);
  }

  function envoyer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    appliquer(valeur, true);
    if (valeur.trim().length === 1) champ.current?.focus();
  }

  function effacer() {
    setValeur("");
    appliquer("", true);
    champ.current?.focus();
  }

  return (
    <form role="search" aria-label={libelle} className={["recherche-liste-form", className].filter(Boolean).join(" ")} onSubmit={envoyer} noValidate>
      <div className={["et-field", message && "et-field-error"].filter(Boolean).join(" ")}>
        <label className="et-field-label" htmlFor={id}>
          {libelle}
        </label>
        <div className="recherche-saisie">
          <input
            ref={champ}
            id={id}
            name="q"
            type="search"
            className="et-input"
            placeholder={placeholder}
            autoComplete="off"
            maxLength={LONGUEUR_MAX_RECHERCHE}
            value={valeur}
            aria-invalid={message ? true : undefined}
            aria-describedby={message ? `${id}-erreur` : undefined}
            onChange={(event) => saisir(event.target.value)}
          />
          {valeur ? (
            <button type="button" className="et-btn et-btn-quiet recherche-effacer" onClick={effacer}>
              <Icon name="close" />
              Effacer
            </button>
          ) : null}
        </div>
        {message ? (
          <span className="et-field-hint" id={`${id}-erreur`} role="alert">
            {message}
          </span>
        ) : null}
      </div>
      <p className="caption recherche-liste-total" role="status" aria-live="polite">
        {recherche && total !== null ? `${annonceResultats(total)} pour « ${recherche} »` : ""}
      </p>
    </form>
  );
}
