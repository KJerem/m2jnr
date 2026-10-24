"use client";

import { useEffect, useEffectEvent, useId, useRef, type ReactNode, type RefObject } from "react";

const FOCUSABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface ModalProps {
  titre: string;
  onClose: () => void;
  children: ReactNode;
  /** Boutons du pied de la fenêtre. */
  actions?: ReactNode;
  /**
   * Élément qui reçoit le focus à la fermeture, en général le bouton qui a déclenché
   * l'ouverture. À fournir quand ce bouton est désactivé pendant un envoi : le navigateur lui
   * retire alors le focus (qui part sur <body>) avant que la fenêtre ne s'ouvre.
   */
  retourFocus?: RefObject<HTMLElement | null>;
}

/**
 * Fenêtre modale accessible : role="dialog" et aria-modal, titre annoncé, focus placé dans la
 * fenêtre et gardé à l'intérieur (Tab et Maj+Tab bouclent), Échap ferme, et le focus revient
 * à l'élément qui l'a ouverte (`retourFocus`, sinon l'élément actif à l'ouverture s'il n'est
 * pas <body>).
 */
export function Modal({ titre, onClose, children, actions, retourFocus }: ModalProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titreId = useId();
  const fermer = useEffectEvent(onClose);
  const cibleDeRetour = useEffectEvent((precedent: HTMLElement | null) => {
    const cible = retourFocus?.current;
    if (cible && cible.isConnected) return cible;
    return precedent && precedent !== document.body && precedent.isConnected ? precedent : null;
  });

  useEffect(() => {
    const dialogue = ref.current;
    if (!dialogue) return;
    const precedent = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusables = () => Array.from(dialogue.querySelectorAll<HTMLElement>(FOCUSABLES));
    // Le focus va sur la fenêtre : le lecteur d'écran annonce le titre puis le contenu.
    dialogue.focus();

    function surTouche(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        fermer();
        return;
      }
      if (event.key !== "Tab") return;
      const liste = focusables();
      const premier = liste[0];
      const dernier = liste[liste.length - 1];
      event.preventDefault();
      if (!premier || !dernier) return;
      const indice = liste.indexOf(document.activeElement as HTMLElement);
      if (event.shiftKey) {
        (indice <= 0 ? dernier : liste[indice - 1])?.focus();
      } else {
        (indice === -1 || indice === liste.length - 1 ? premier : liste[indice + 1])?.focus();
      }
    }

    document.addEventListener("keydown", surTouche);
    return () => {
      document.removeEventListener("keydown", surTouche);
      cibleDeRetour(precedent)?.focus();
    };
  }, []);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div ref={ref} className="modal" role="dialog" aria-modal="true" aria-labelledby={titreId} tabIndex={-1}>
        <div className="panel-head">
          <h2 id={titreId}>{titre}</h2>
        </div>
        <div className="panel-body">{children}</div>
        {actions ? <div className="modal-actions">{actions}</div> : null}
      </div>
    </div>
  );
}
