"use client";

import type { RefObject } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import type { ClientResume } from "@/lib/clients";
import { nomComplet } from "@/lib/format";

export interface DoublonDialogProps {
  clients: ClientResume[];
  libelleConfirmer: string;
  envoi: boolean;
  onConfirmer: () => void;
  onAnnuler: () => void;
  /** Bouton d'envoi du formulaire, qui reprend le focus à la fermeture. */
  retourFocus?: RefObject<HTMLElement | null>;
}

/** Alerte de doublon : le téléphone saisi appartient déjà à un ou plusieurs clients. */
export function DoublonDialog({ clients, libelleConfirmer, envoi, onConfirmer, onAnnuler, retourFocus }: DoublonDialogProps) {
  return (
    <Modal
      titre="Téléphone déjà enregistré"
      onClose={onAnnuler}
      retourFocus={retourFocus}
      actions={
        <>
          <Button onClick={onAnnuler}>Annuler</Button>
          <Button variant="primary" onClick={onConfirmer} loading={envoi}>
            {libelleConfirmer}
          </Button>
        </>
      }
    >
      <p>Un client avec ce téléphone existe déjà. Vérifiez qu&apos;il ne s&apos;agit pas de la même personne.</p>
      <ul className="doublons">
        {clients.map((client) => (
          <li key={client.id}>
            <a href={`/clients/${client.id}`} target="_blank" rel="noopener">
              {nomComplet(client)}
              <span className="sr-only"> (ouvre la fiche dans un nouvel onglet)</span>
            </a>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
