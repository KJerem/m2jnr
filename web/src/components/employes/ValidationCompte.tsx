"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import { cleEmploye, de, type Employe } from "@/lib/employes";
import { formatDateHeureOuAnnee } from "@/lib/format";
import { LIBELLE_ROLE, type Role } from "@/lib/session";
import { rafraichirApresCompte } from "./actions";

/**
 * Inscription en attente (story S8.3) : le gérant choisit le rôle définitif (mécanicien par
 * défaut, le moins de droits) puis valide le compte, ou refuse la demande après confirmation
 * (elle est alors supprimée).
 */
export function ValidationCompte({ employe, onValide }: { employe: Employe; onValide: () => void }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const notifier = useToast();
  const idRole = useId();
  const boutonRefuser = useRef<HTMLButtonElement>(null);
  const [role, setRole] = useState<Role>("mecanicien");
  const [confirmerRefus, setConfirmerRefus] = useState(false);
  const nom = employe.nom_affiche;

  const validation = useMutation({
    mutationFn: () => apiFetch<Employe>(`/utilisateurs/${employe.id}/valider`, { method: "POST", body: { role } }),
    onSuccess: (maj) => {
      queryClient.setQueryData(cleEmploye(employe.id), maj);
      notifier({ type: "success", message: `Compte ${de(maj.nom_affiche)} validé : ${LIBELLE_ROLE[maj.role].toLowerCase()}.` });
      onValide();
    },
    onError: (erreur) => notifier({ type: "error", message: erreur.message }),
    onSettled: () => rafraichirApresCompte(queryClient),
  });

  const refus = useMutation({
    mutationFn: () => apiFetch<void>(`/utilisateurs/${employe.id}/refuser`, { method: "POST" }),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: cleEmploye(employe.id) });
      notifier({ type: "success", message: `Demande ${de(nom)} refusée.` });
      router.push("/employes");
    },
    onError: (erreur) => {
      setConfirmerRefus(false);
      notifier({ type: "error", message: erreur.message });
    },
    onSettled: () => rafraichirApresCompte(queryClient),
  });

  return (
    <div className="stack">
      <p>
        Demande d&apos;inscription reçue le {formatDateHeureOuAnnee(employe.cree_le)}, rôle demandé : {LIBELLE_ROLE[employe.role].toLowerCase()}. Le compte ne
        peut pas se connecter avant sa validation.
      </p>
      <div className="et-field">
        <label className="et-field-label" htmlFor={idRole}>
          Rôle du compte
        </label>
        <select id={idRole} className="et-input" value={role} onChange={(event) => setRole(event.target.value as Role)}>
          <option value="mecanicien">Mécanicien</option>
          <option value="gerant">Gérant</option>
        </select>
      </div>
      <div className="actions">
        <Button variant="primary" loading={validation.isPending} onClick={() => validation.mutate()}>
          Valider le compte
        </Button>
        <Button ref={boutonRefuser} variant="danger" onClick={() => setConfirmerRefus(true)}>
          Refuser
        </Button>
      </div>
      {confirmerRefus ? (
        <Modal
          titre={`Refuser la demande ${de(nom)} ?`}
          onClose={() => setConfirmerRefus(false)}
          retourFocus={boutonRefuser}
          actions={
            <>
              <Button onClick={() => setConfirmerRefus(false)}>Annuler</Button>
              <Button variant="danger" loading={refus.isPending} onClick={() => refus.mutate()}>
                Refuser la demande
              </Button>
            </>
          }
        >
          <p>La demande est supprimée : la personne ne pourra pas se connecter. Elle pourra refaire une demande avec la même adresse.</p>
        </Modal>
      ) : null}
    </div>
  );
}
