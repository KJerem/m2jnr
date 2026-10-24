"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { ApiError } from "@/lib/api";
import { CLIENT_VIDE, clientSchema, versEntree, type Client, type ClientEntree, type ClientFormValues, type ClientResume } from "@/lib/clients";
import { appliquerErreursApi } from "@/lib/formulaires";
import { DoublonDialog } from "./DoublonDialog";

const CHAMPS = ["nom", "prenom", "telephone", "email", "consentement_rappels"] as const;

export interface ClientFormProps {
  mode: "creation" | "modification";
  valeursInitiales?: ClientFormValues;
  /** Appel à l'API ; `confirmerDoublon` vrai après l'alerte de doublon. */
  envoyer: (entree: ClientEntree, confirmerDoublon: boolean) => Promise<Client>;
  onSucces: (client: Client) => void;
  onAnnuler?: () => void;
}

export function ClientForm({ mode, valeursInitiales = CLIENT_VIDE, envoyer, onSucces, onAnnuler }: ClientFormProps) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ClientFormValues>({ resolver: zodResolver(clientSchema), defaultValues: valeursInitiales });
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);
  const [doublons, setDoublons] = useState<{ entree: ClientEntree; clients: ClientResume[] } | null>(null);
  const [confirmation, setConfirmation] = useState(false);

  async function enregistrer(entree: ClientEntree, confirmerDoublon: boolean) {
    setErreurGenerale(null);
    try {
      const client = await envoyer(entree, confirmerDoublon);
      setDoublons(null);
      onSucces(client);
    } catch (erreur) {
      if (erreur instanceof ApiError && erreur.code === "doublon_telephone") {
        setDoublons({ entree, clients: (erreur.details.clients as ClientResume[] | undefined) ?? [] });
        return;
      }
      setDoublons(null);
      setErreurGenerale(appliquerErreursApi(erreur, CHAMPS, setError));
    }
  }

  async function confirmerDoublon() {
    if (!doublons) return;
    setConfirmation(true);
    await enregistrer(doublons.entree, true);
    setConfirmation(false);
  }

  const creation = mode === "creation";

  return (
    <form className="stack" noValidate onSubmit={handleSubmit((valeurs) => enregistrer(versEntree(valeurs), false))}>
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <div className="form-grid">
        <TextField label="Nom" required autoComplete="family-name" maxLength={100} error={errors.nom?.message} {...register("nom")} />
        <TextField label="Prénom" autoComplete="given-name" maxLength={100} error={errors.prenom?.message} {...register("prenom")} />
        <TextField
          label="Téléphone"
          required
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          hint="Par exemple 06 12 34 56 78"
          error={errors.telephone?.message}
          {...register("telephone")}
        />
        <TextField
          label="E-mail"
          type="email"
          inputMode="email"
          autoComplete="email"
          hint="Facultatif"
          error={errors.email?.message}
          {...register("email")}
        />
      </div>
      <label className="et-check">
        <input type="checkbox" {...register("consentement_rappels")} />
        Le client accepte de recevoir des rappels d&apos;entretien
      </label>
      <div className="actions">
        <Button type="submit" variant="primary" loading={isSubmitting && !doublons}>
          {creation ? "Créer le client" : "Enregistrer"}
        </Button>
        {onAnnuler ? <Button onClick={onAnnuler}>Annuler</Button> : null}
      </div>
      {doublons ? (
        <DoublonDialog
          clients={doublons.clients}
          libelleConfirmer={creation ? "Créer quand même" : "Enregistrer quand même"}
          envoi={confirmation}
          onConfirmer={confirmerDoublon}
          onAnnuler={() => setDoublons(null)}
        />
      ) : null}
    </form>
  );
}
