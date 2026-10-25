"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";
import { AIDE_MOT_DE_PASSE, de, EMPLOYE_VIDE, employeCreationSchema, versEntreeEmploye, type Employe, type EmployeCreationValeurs } from "@/lib/employes";
import { appliquerErreursApi } from "@/lib/formulaires";
import { rafraichirApresCompte } from "./actions";

const CHAMPS = ["prenom", "nom", "email", "role", "mot_de_passe"] as const;

export function creerEmploye(valeurs: EmployeCreationValeurs) {
  return apiFetch<Employe>("/utilisateurs", { method: "POST", body: { ...versEntreeEmploye(valeurs), mot_de_passe: valeurs.mot_de_passe } });
}

/** Formulaire « Nouvel employé » : le compte est actif dès sa création. */
export function EmployeCreationForm({ onSucces, onAnnuler }: { onSucces: (employe: Employe) => void; onAnnuler: () => void }) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EmployeCreationValeurs>({ resolver: zodResolver(employeCreationSchema), defaultValues: EMPLOYE_VIDE });
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);

  async function enregistrer(valeurs: EmployeCreationValeurs) {
    setErreurGenerale(null);
    try {
      onSucces(await creerEmploye(valeurs));
    } catch (erreur) {
      setErreurGenerale(appliquerErreursApi(erreur, CHAMPS, setError));
    }
  }

  return (
    <form className="stack" noValidate onSubmit={handleSubmit(enregistrer)}>
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <div className="form-grid">
        <TextField label="Prénom" required autoComplete="off" maxLength={100} error={errors.prenom?.message} {...register("prenom")} />
        <TextField label="Nom" required autoComplete="off" maxLength={100} error={errors.nom?.message} {...register("nom")} />
        <TextField label="E-mail" required type="email" inputMode="email" autoComplete="off" hint="Sert d'identifiant de connexion." error={errors.email?.message} {...register("email")} />
        <SelectField label="Rôle" required error={errors.role?.message} {...register("role")}>
          <option value="mecanicien">Mécanicien</option>
          <option value="gerant">Gérant</option>
        </SelectField>
        <TextField label="Mot de passe" required type="password" autoComplete="new-password" hint={AIDE_MOT_DE_PASSE} error={errors.mot_de_passe?.message} {...register("mot_de_passe")} />
        <TextField label="Confirmer le mot de passe" required type="password" autoComplete="new-password" error={errors.confirmation?.message} {...register("confirmation")} />
      </div>
      <p className="caption">Transmettez le mot de passe à l&apos;employé de vive voix ; l&apos;application ne l&apos;affiche plus ensuite.</p>
      <div className="actions">
        <Button type="submit" variant="primary" loading={isSubmitting}>
          Créer le compte
        </Button>
        <Button onClick={onAnnuler}>Annuler</Button>
      </div>
    </form>
  );
}

export function NouvelEmploye() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const notifier = useToast();

  return (
    <>
      <header className="page-head">
        <div>
          <p className="breadcrumb">
            <Link href="/employes">Employés</Link> / Nouveau
          </p>
          <h1 className="display">Nouvel employé</h1>
        </div>
      </header>
      <section className="panel">
        <div className="panel-body">
          <EmployeCreationForm
            onSucces={(employe) => {
              void rafraichirApresCompte(queryClient);
              notifier({ type: "success", message: `Compte ${de(employe.nom_affiche)} créé.` });
              router.push(`/employes/${employe.id}`);
            }}
            onAnnuler={() => router.push("/employes")}
          />
        </div>
      </section>
    </>
  );
}
