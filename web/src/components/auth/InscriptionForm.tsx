"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { SESSION_KEY } from "@/components/session/useSession";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { apiFetch } from "@/lib/api";
import { AIDE_MOT_DE_PASSE } from "@/lib/employes";
import { appliquerErreursApi } from "@/lib/formulaires";
import { INSCRIPTION_VIDE, inscriptionSchema, versEntreeInscription, type EtatInscription, type InscriptionReponse, type InscriptionValeurs } from "@/lib/inscription";
import { PAGE_CONNEXION } from "@/lib/session";

const CHAMPS = ["prenom", "nom", "email", "mot_de_passe"] as const;

/**
 * Inscription autonome d'un gérant (story S8.3). Le tout premier compte du garage est créé
 * actif et connecté (redirection vers l'accueil) ; sinon la demande attend la validation d'un
 * gérant et un panneau de confirmation affiche le message neutre de l'API, le même que l'e-mail
 * soit déjà connu ou non.
 */
export function InscriptionForm() {
  const router = useRouter();
  const client = useQueryClient();
  const [demande, setDemande] = useState<string | null>(null);
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);
  const titreConfirmation = useRef<HTMLHeadingElement>(null);
  const { data: etat } = useQuery({
    queryKey: ["inscription", "etat"],
    queryFn: ({ signal }) => apiFetch<EtatInscription>("/auth/inscription", { signal, redirigerSi401: false }),
  });
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<InscriptionValeurs>({ resolver: zodResolver(inscriptionSchema), defaultValues: INSCRIPTION_VIDE });

  useEffect(() => {
    if (demande) titreConfirmation.current?.focus();
  }, [demande]);

  async function inscrire(valeurs: InscriptionValeurs) {
    setErreurGenerale(null);
    try {
      const reponse = await apiFetch<InscriptionReponse>("/auth/register", { method: "POST", body: versEntreeInscription(valeurs), redirigerSi401: false });
      if (reponse.compte_actif && reponse.utilisateur) {
        client.setQueryData(SESSION_KEY, { utilisateur: reponse.utilisateur });
        router.replace("/");
        router.refresh();
        return;
      }
      setDemande(reponse.message);
    } catch (erreur) {
      setErreurGenerale(appliquerErreursApi(erreur, CHAMPS, setError));
    }
  }

  if (demande) {
    return (
      <div className="stack" role="status">
        <h2 ref={titreConfirmation} tabIndex={-1}>
          Demande envoyée
        </h2>
        <p className="callout callout-info">{demande}</p>
        <p>
          <Link href={PAGE_CONNEXION}>Retour à la connexion</Link>
        </p>
      </div>
    );
  }

  return (
    <form className="stack" noValidate onSubmit={handleSubmit(inscrire)}>
      {etat ? (
        <p className="caption">
          {etat.premier_compte
            ? "Premier compte du garage : il est créé gérant et ouvert tout de suite."
            : "Votre compte sera utilisable après sa validation par un gérant du garage."}
        </p>
      ) : null}
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <TextField label="Prénom" required autoComplete="given-name" maxLength={100} error={errors.prenom?.message} {...register("prenom")} />
      <TextField label="Nom" required autoComplete="family-name" maxLength={100} error={errors.nom?.message} {...register("nom")} />
      <TextField label="E-mail" required type="email" inputMode="email" autoComplete="email" hint="Sert d'identifiant de connexion." error={errors.email?.message} {...register("email")} />
      <TextField label="Mot de passe" required type="password" autoComplete="new-password" hint={AIDE_MOT_DE_PASSE} error={errors.mot_de_passe?.message} {...register("mot_de_passe")} />
      <TextField label="Confirmer le mot de passe" required type="password" autoComplete="new-password" error={errors.confirmation?.message} {...register("confirmation")} />
      <Button type="submit" variant="primary" block loading={isSubmitting}>
        Créer le compte
      </Button>
      <p className="caption">
        <Link href={PAGE_CONNEXION}>J&apos;ai déjà un compte</Link>
      </p>
    </form>
  );
}
