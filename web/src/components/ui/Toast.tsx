"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

export interface Notification {
  type: "success" | "error";
  message: string;
}

interface ToastAffiche extends Notification {
  id: number;
}

const DUREE_MS = 6000;
const ContexteToast = createContext<(notification: Notification) => void>(() => {});

/** Notifie une action terminée (« OT-2026-001 : En cours ») ou une erreur, sans voler le focus. */
export function useToast() {
  return useContext(ContexteToast);
}

/**
 * Notifications éphémères. Les deux zones live existent dès le rendu (sinon les lecteurs
 * d'écran n'annoncent pas le premier message) : « polite » pour les succès, « alert » pour
 * les erreurs. Chaque message se ferme seul après 6 s ou avec son bouton.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastAffiche[]>([]);
  const compteur = useRef(0);

  const fermer = useCallback((id: number) => setToasts((liste) => liste.filter((t) => t.id !== id)), []);
  const notifier = useCallback(
    (notification: Notification) => {
      compteur.current += 1;
      const id = compteur.current;
      setToasts((liste) => [...liste.slice(-3), { ...notification, id }]);
      window.setTimeout(() => fermer(id), DUREE_MS);
    },
    [fermer],
  );

  const zone = (type: Notification["type"]) =>
    toasts
      .filter((t) => t.type === type)
      .map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span>{t.message}</span>
          <button type="button" className="toast-fermer" onClick={() => fermer(t.id)} aria-label="Fermer la notification">
            ×
          </button>
        </div>
      ));

  return (
    <ContexteToast.Provider value={notifier}>
      {children}
      <div className="toasts">
        <div role="status" aria-live="polite" className="toasts-zone">
          {zone("success")}
        </div>
        <div role="alert" className="toasts-zone">
          {zone("error")}
        </div>
      </div>
    </ContexteToast.Provider>
  );
}
