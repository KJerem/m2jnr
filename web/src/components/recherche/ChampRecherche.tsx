"use client";

import { useRouter } from "next/navigation";
import { useId, useRef, useState, type FormEvent } from "react";
import { Icon } from "@/components/ui/Icon";
import { erreurSaisie, lienRecherche, LONGUEUR_MAX, PLACEHOLDER_RECHERCHE } from "@/lib/recherche";

export interface ChampRechercheProps {
  /** Saisie affichée au départ (page de résultats). */
  valeurInitiale?: string;
  /** Erreur renvoyée par l'API (422 sur « q »), affichée sous le champ. */
  erreurServeur?: string | null;
  className?: string;
}

/**
 * Champ de recherche du gérant (maquette 4) : étiquette « Rechercher » visible, recherche
 * lancée par Entrée ou par le bouton loupe, vers /recherche?q=…. Une saisie trop courte est
 * signalée sous le champ, sans quitter la page.
 */
export function ChampRecherche({ valeurInitiale = "", erreurServeur = null, className }: ChampRechercheProps) {
  const router = useRouter();
  const id = useId();
  const champ = useRef<HTMLInputElement>(null);
  const [valeur, setValeur] = useState(valeurInitiale);
  const [erreur, setErreur] = useState<string | null>(null);
  const message = erreur ?? erreurServeur;

  function envoyer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const probleme = erreurSaisie(valeur);
    if (probleme) {
      setErreur(probleme);
      champ.current?.focus();
      return;
    }
    setErreur(null);
    router.push(lienRecherche(valeur));
  }

  return (
    <form role="search" className={["recherche-form", className].filter(Boolean).join(" ")} onSubmit={envoyer} noValidate>
      <div className={["et-field", message && "et-field-error"].filter(Boolean).join(" ")}>
        <label className="et-field-label" htmlFor={id}>
          Rechercher
        </label>
        <div className="recherche-saisie">
          <input
            ref={champ}
            id={id}
            name="q"
            type="search"
            className="et-input"
            placeholder={PLACEHOLDER_RECHERCHE}
            autoComplete="off"
            maxLength={LONGUEUR_MAX}
            value={valeur}
            aria-invalid={message ? true : undefined}
            aria-describedby={message ? `${id}-erreur` : undefined}
            onChange={(event) => {
              setValeur(event.target.value);
              if (erreur) setErreur(null);
            }}
          />
          <button type="submit" className="et-btn et-btn-secondary recherche-bouton" aria-label="Lancer la recherche" title="Lancer la recherche">
            <Icon name="search" />
          </button>
        </div>
        {message ? (
          <span className="et-field-hint" id={`${id}-erreur`} role="alert">
            {message}
          </span>
        ) : null}
      </div>
    </form>
  );
}
