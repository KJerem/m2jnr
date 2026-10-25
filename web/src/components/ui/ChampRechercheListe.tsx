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
  /**
   * Recherche de l'adresse (?q=). Quand elle change sans passer par ce champ (retour arrière,
   * lien du menu), le champ la reprend.
   */
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
 * qui rend le focus au champ, nombre de résultats annoncé (aria-live polite) ; une saisie en
 * attente est appliquée dès que le champ perd le focus. La liste qui
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

  // Recherche de l'adresse changée par une navigation : le champ la reprend. Celle que ce
  // champ vient de transmettre revient aussi par là, et ne touche pas à la saisie en cours.
  const [initialeVue, setInitialeVue] = useState(valeurInitiale.trim());
  const initiale = valeurInitiale.trim();
  if (initiale !== initialeVue) {
    setInitialeVue(initiale);
    if (initiale !== recherche) {
      setValeur(initiale);
      setRecherche(initiale);
      setErreur(null);
    }
  }

  useEffect(() => {
    rappel.current = onRecherche;
  });
  useEffect(() => {
    transmise.current = recherche;
  }, [recherche]);
  useEffect(() => () => window.clearTimeout(minuteur.current), []);

  function appliquer(saisie: string, immediat: boolean) {
    window.clearTimeout(minuteur.current);
    minuteur.current = undefined;
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

  // Saisie encore en attente quand le champ perd le focus (clic sur une ligne, un filtre) :
  // appliquée tout de suite. Appliquée après le clic, la mise à jour de l'adresse
  // (replaceState) annulerait la navigation vers la ligne choisie.
  function quitter() {
    if (minuteur.current !== undefined) appliquer(valeur, false);
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
            onBlur={quitter}
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
