"use client";

import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface Onglet {
  id: string;
  libelle: string;
  contenu: ReactNode;
}

export interface OngletsProps {
  /** Nom de l'ensemble d'onglets, annoncé par les lecteurs d'écran. */
  label: string;
  onglets: Onglet[];
  initial?: string;
  /** Mode contrôlé : onglet affiché et changement demandé (sinon état interne). */
  actif?: string;
  onChange?: (id: string) => void;
}

/**
 * Onglets accessibles (motif ARIA « tabs ») : role tablist / tab / tabpanel, un seul onglet
 * dans l'ordre de tabulation (tabindex mobile), flèches gauche et droite (en boucle), Début et
 * Fin ; l'onglet atteint au clavier est aussitôt affiché.
 */
export function Onglets({ label, onglets, initial, actif: actifControle, onChange }: OngletsProps) {
  const base = useId();
  const [actifInterne, setActifInterne] = useState(initial ?? onglets[0]?.id);
  const actif = actifControle ?? actifInterne;
  const boutons = useRef<(HTMLButtonElement | null)[]>([]);

  function setActif(id: string) {
    setActifInterne(id);
    onChange?.(id);
  }

  function activer(index: number) {
    const cible = onglets[(index + onglets.length) % onglets.length];
    if (!cible) return;
    setActif(cible.id);
    boutons.current[(index + onglets.length) % onglets.length]?.focus();
  }

  function surTouche(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const actions: Record<string, () => void> = {
      ArrowRight: () => activer(index + 1),
      ArrowLeft: () => activer(index - 1),
      Home: () => activer(0),
      End: () => activer(onglets.length - 1),
    };
    const action = actions[event.key];
    if (action) {
      event.preventDefault();
      action();
    }
  }

  return (
    <div className="onglets">
      <div role="tablist" aria-label={label} className="onglets-liste">
        {onglets.map((o, i) => (
          <button
            key={o.id}
            ref={(el) => {
              boutons.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${base}-onglet-${o.id}`}
            aria-selected={actif === o.id}
            aria-controls={`${base}-panneau-${o.id}`}
            tabIndex={actif === o.id ? 0 : -1}
            className="onglet"
            onClick={() => setActif(o.id)}
            onKeyDown={(event) => surTouche(event, i)}
          >
            {o.libelle}
          </button>
        ))}
      </div>
      {onglets.map((o) => (
        <div key={o.id} role="tabpanel" id={`${base}-panneau-${o.id}`} aria-labelledby={`${base}-onglet-${o.id}`} hidden={actif !== o.id} tabIndex={0} className="onglet-panneau">
          {actif === o.id ? o.contenu : null}
        </div>
      ))}
    </div>
  );
}
