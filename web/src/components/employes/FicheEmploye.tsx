"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useSession } from "@/components/session/useSession";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import {
  AIDE_MOT_DE_PASSE,
  cleEmploye,
  employeModificationSchema,
  libelleDerniereConnexion,
  motDePasseSchema,
  versEntreeEmploye,
  versFormulaireEmploye,
  type Employe,
  type EmployeModificationValeurs,
  type MotDePasseValeurs,
} from "@/lib/employes";
import { formatDateHeureOuAnnee } from "@/lib/format";
import { appliquerErreursApi } from "@/lib/formulaires";
import { LIBELLE_ROLE } from "@/lib/session";
import { rafraichirApresCompte } from "./actions";
import { BadgeCompte } from "./BadgeCompte";

export const MESSAGE_SOI_MEME_ROLE = "Vous ne pouvez pas changer votre propre rôle.";
export const MESSAGE_SOI_MEME_DESACTIVER = "Vous ne pouvez pas désactiver votre propre compte : un autre gérant doit le faire.";

type Confirmation = "desactiver" | "reactiver" | null;

/** Fiche d'un employé (story S8.2) : détails, modification, mot de passe, blocage, accès. */
export function FicheEmploye({ employeId }: { employeId: number }) {
  const queryClient = useQueryClient();
  const notifier = useToast();
  const { utilisateur } = useSession();
  const [edition, setEdition] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation>(null);
  const [motDePasse, setMotDePasse] = useState(false);
  const titreAcces = useRef<HTMLHeadingElement>(null);
  const titre = useRef<HTMLHeadingElement>(null);
  const cle = cleEmploye(employeId);
  const { data: employe, isPending, isError, error } = useQuery({
    queryKey: cle,
    queryFn: ({ signal }) => apiFetch<Employe>(`/utilisateurs/${employeId}`, { signal }),
  });

  const action = useMutation({
    mutationFn: ({ chemin, corps }: { chemin: string; corps?: unknown; succes: (e: Employe) => string }) =>
      apiFetch<Employe>(`/utilisateurs/${employeId}/${chemin}`, { method: "POST", body: corps }),
    onSuccess: (maj, { succes }) => {
      queryClient.setQueryData(cle, maj);
      notifier({ type: "success", message: succes(maj) });
      setConfirmation(null);
      setMotDePasse(false);
      // Le bouton qui a lancé l'action peut avoir disparu (Désactiver → Réactiver) : le focus
      // va au titre de la section, lu par le lecteur d'écran.
      window.setTimeout(() => titreAcces.current?.focus(), 0);
    },
    onError: (erreur) => notifier({ type: "error", message: erreur.message }),
    onSettled: () => rafraichirApresCompte(queryClient),
  });

  if (isPending) {
    return (
      <p className="muted" role="status">
        Chargement de la fiche…
      </p>
    );
  }
  if (isError) {
    return (
      <div className="stack">
        <p className="callout callout-danger" role="alert">
          {error.message}
        </p>
        <p>
          <Link href="/employes">Retour à la liste des employés</Link>
        </p>
      </div>
    );
  }

  const soiMeme = utilisateur?.id === employe.id;
  const nom = employe.nom_affiche;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="breadcrumb">
            <Link href="/employes">Employés</Link> / Fiche
          </p>
          <h1 className="display" ref={titre} tabIndex={-1}>
            {nom}
          </h1>
          <p className="row sub">
            <span className="caption">{LIBELLE_ROLE[employe.role]}</span>
            <BadgeCompte employe={employe} />
          </p>
        </div>
        {!edition && employe.statut !== "en_attente" ? <Button onClick={() => setEdition(true)}>Modifier</Button> : null}
      </header>

      <div className="grid-2">
        <section className="panel" aria-labelledby="titre-compte">
          <div className="panel-head">
            <h2 id="titre-compte">Compte</h2>
          </div>
          <div className="panel-body">
            {edition ? (
              <EmployeModificationForm
                employe={employe}
                soiMeme={soiMeme}
                onSucces={(maj) => {
                  queryClient.setQueryData(cle, maj);
                  void rafraichirApresCompte(queryClient);
                  notifier({ type: "success", message: `Compte de ${maj.nom_affiche} enregistré.` });
                  setEdition(false);
                  window.setTimeout(() => titre.current?.focus(), 0);
                }}
                onAnnuler={() => setEdition(false)}
              />
            ) : (
              <dl className="dl">
                <dt>Prénom</dt>
                <dd>{employe.prenom}</dd>
                <dt>Nom</dt>
                <dd>{employe.nom || <span className="muted">Non renseigné</span>}</dd>
                <dt>E-mail</dt>
                <dd className="cellule-email">{employe.email}</dd>
                <dt>Rôle</dt>
                <dd>{LIBELLE_ROLE[employe.role]}</dd>
                <dt>Créé le</dt>
                <dd>{formatDateHeureOuAnnee(employe.cree_le)}</dd>
                <dt>Dernière connexion</dt>
                <dd>{libelleDerniereConnexion(employe)}</dd>
                {employe.valide_le ? (
                  <>
                    <dt>Validé le</dt>
                    <dd>{formatDateHeureOuAnnee(employe.valide_le)}</dd>
                  </>
                ) : null}
                {employe.statut === "desactive" && employe.desactive_le ? (
                  <>
                    <dt>Désactivé le</dt>
                    <dd>{formatDateHeureOuAnnee(employe.desactive_le)}</dd>
                  </>
                ) : null}
              </dl>
            )}
          </div>
        </section>

        <section className="panel" aria-labelledby="titre-acces">
          <div className="panel-head">
            <h2 id="titre-acces" ref={titreAcces} tabIndex={-1}>
              Accès
            </h2>
          </div>
          <div className="panel-body">
            {employe.statut === "en_attente" ? (
              <p className="muted">Ce compte attend la validation d&apos;un gérant.</p>
            ) : (
              <>
                <div className="stack-sm">
                  <Button onClick={() => setMotDePasse(true)}>Réinitialiser le mot de passe</Button>
                  <span className="caption">Le compte est aussi débloqué.</span>
                </div>
                {employe.bloque_jusqu_a ? (
                  <div className="stack-sm">
                    <Button
                      loading={action.isPending && action.variables?.chemin === "debloquer"}
                      onClick={() => action.mutate({ chemin: "debloquer", succes: (e) => `Compte de ${e.nom_affiche} débloqué.` })}
                    >
                      Débloquer
                    </Button>
                    <span className="caption">Bloqué après 5 essais erronés.</span>
                  </div>
                ) : null}
                {employe.statut === "actif" ? (
                  <div className="stack-sm">
                    <Button variant="danger" disabled={soiMeme} aria-describedby={soiMeme ? "aide-desactiver" : undefined} onClick={() => setConfirmation("desactiver")}>
                      Désactiver le compte
                    </Button>
                    <span className="caption" id="aide-desactiver">
                      {soiMeme ? MESSAGE_SOI_MEME_DESACTIVER : "L'employé ne pourra plus se connecter ; ses sessions ouvertes s'arrêtent."}
                    </span>
                  </div>
                ) : (
                  <div className="stack-sm">
                    <Button onClick={() => setConfirmation("reactiver")}>Réactiver le compte</Button>
                    <span className="caption">L&apos;employé pourra de nouveau se connecter avec son mot de passe.</span>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </div>

      {confirmation ? (
        <Modal
          titre={confirmation === "desactiver" ? `Désactiver le compte de ${nom} ?` : `Réactiver le compte de ${nom} ?`}
          onClose={() => setConfirmation(null)}
          actions={
            <>
              <Button onClick={() => setConfirmation(null)}>Annuler</Button>
              <Button
                variant={confirmation === "desactiver" ? "danger" : "primary"}
                loading={action.isPending}
                onClick={() =>
                  action.mutate(
                    confirmation === "desactiver"
                      ? { chemin: "desactiver", succes: (e) => `Compte de ${e.nom_affiche} désactivé.` }
                      : { chemin: "reactiver", succes: (e) => `Compte de ${e.nom_affiche} réactivé.` },
                  )
                }
              >
                {confirmation === "desactiver" ? "Désactiver" : "Réactiver"}
              </Button>
            </>
          }
        >
          <p>
            {confirmation === "desactiver"
              ? "Il ne pourra plus se connecter et sa session en cours s'arrêtera à sa prochaine action. Ses interventions passées restent dans l'historique."
              : "Il pourra de nouveau se connecter avec son mot de passe actuel."}
          </p>
        </Modal>
      ) : null}

      {motDePasse ? (
        <MotDePasseModal
          nom={nom}
          envoi={action.isPending}
          onAnnuler={() => setMotDePasse(false)}
          onValider={(valeurs) => action.mutate({ chemin: "mot-de-passe", corps: { mot_de_passe: valeurs.mot_de_passe }, succes: (e) => `Mot de passe de ${e.nom_affiche} réinitialisé.` })}
        />
      ) : null}
    </>
  );
}

function MotDePasseModal({ nom, envoi, onAnnuler, onValider }: { nom: string; envoi: boolean; onAnnuler: () => void; onValider: (valeurs: MotDePasseValeurs) => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MotDePasseValeurs>({ resolver: zodResolver(motDePasseSchema), defaultValues: { mot_de_passe: "", confirmation: "" } });
  return (
    <Modal titre={`Nouveau mot de passe pour ${nom}`} onClose={onAnnuler}>
      <form className="stack" noValidate onSubmit={handleSubmit(onValider)}>
        <TextField label="Nouveau mot de passe" required type="password" autoComplete="new-password" hint={AIDE_MOT_DE_PASSE} error={errors.mot_de_passe?.message} {...register("mot_de_passe")} />
        <TextField label="Confirmer le mot de passe" required type="password" autoComplete="new-password" error={errors.confirmation?.message} {...register("confirmation")} />
        <p className="caption">Transmettez-le à l&apos;employé de vive voix ; le compte est aussi débloqué.</p>
        <div className="actions modal-form-actions">
          <Button onClick={onAnnuler}>Annuler</Button>
          <Button type="submit" variant="primary" loading={envoi}>
            Enregistrer le mot de passe
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const CHAMPS = ["prenom", "nom", "email", "role"] as const;

function EmployeModificationForm({ employe, soiMeme, onSucces, onAnnuler }: { employe: Employe; soiMeme: boolean; onSucces: (e: Employe) => void; onAnnuler: () => void }) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EmployeModificationValeurs>({ resolver: zodResolver(employeModificationSchema), defaultValues: versFormulaireEmploye(employe) });
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);

  async function enregistrer(valeurs: EmployeModificationValeurs) {
    setErreurGenerale(null);
    try {
      onSucces(await apiFetch<Employe>(`/utilisateurs/${employe.id}`, { method: "PUT", body: versEntreeEmploye(valeurs) }));
    } catch (erreur) {
      setErreurGenerale(appliquerErreursApi(erreur, CHAMPS, setError));
    }
  }

  return (
    <form className="stack" noValidate onSubmit={handleSubmit(enregistrer)}>
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <TextField label="Prénom" required maxLength={100} autoComplete="off" error={errors.prenom?.message} {...register("prenom")} />
      <TextField label="Nom" required maxLength={100} autoComplete="off" error={errors.nom?.message} {...register("nom")} />
      <TextField label="E-mail" required type="email" inputMode="email" autoComplete="off" error={errors.email?.message} {...register("email")} />
      {soiMeme ? (
        // Rôle non modifiable par soi-même : affiché, non envoyé autrement que tel quel.
        <div className="et-field">
          <span className="et-field-label">Rôle</span>
          <span>{LIBELLE_ROLE[employe.role]}</span>
          <span className="et-field-hint">{MESSAGE_SOI_MEME_ROLE}</span>
        </div>
      ) : (
        <SelectField label="Rôle" required error={errors.role?.message} {...register("role")}>
          <option value="mecanicien">Mécanicien</option>
          <option value="gerant">Gérant</option>
        </SelectField>
      )}
      <div className="actions">
        <Button type="submit" variant="primary" loading={isSubmitting}>
          Enregistrer
        </Button>
        <Button onClick={onAnnuler}>Annuler</Button>
      </div>
    </form>
  );
}
