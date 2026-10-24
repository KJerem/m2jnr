"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type FocusEvent } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/Field";
import { ApiError } from "@/lib/api";
import { appliquerErreursApi } from "@/lib/formulaires";
import {
  aujourdHui,
  normaliserImmatriculation,
  normaliserVin,
  VEHICULE_VIDE,
  vehiculeSchema,
  versEntreeVehicule,
  type Vehicule,
  type VehiculeEntree,
  type VehiculeFormValues,
} from "@/lib/vehicules";

const CHAMPS = ["immatriculation", "marque", "modele", "kilometrage", "vin", "date_mise_en_circulation"] as const;

export interface VehiculeFormProps {
  mode: "creation" | "modification";
  valeursInitiales?: VehiculeFormValues;
  envoyer: (entree: VehiculeEntree) => Promise<Vehicule>;
  onSucces: (vehicule: Vehicule) => void;
  onAnnuler?: () => void;
}

export function VehiculeForm({ mode, valeursInitiales = VEHICULE_VIDE, envoyer, onSucces, onAnnuler }: VehiculeFormProps) {
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<VehiculeFormValues>({ resolver: zodResolver(vehiculeSchema), defaultValues: valeursInitiales });
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);

  async function enregistrer(valeurs: VehiculeFormValues) {
    setErreurGenerale(null);
    try {
      onSucces(await envoyer(versEntreeVehicule(valeurs)));
    } catch (erreur) {
      if (erreur instanceof ApiError && erreur.code === "immatriculation_existante") {
        setError("immatriculation", { type: "server", message: erreur.message }, { shouldFocus: true });
        return;
      }
      setErreurGenerale(appliquerErreursApi(erreur, CHAMPS, setError));
    }
  }

  // La plaque et le VIN s'affichent normalisés dès qu'on quitte le champ : on voit ce qui sera enregistré.
  const immatriculation = register("immatriculation", {
    onBlur: (event: FocusEvent<HTMLInputElement>) => {
      const normalisee = normaliserImmatriculation(event.target.value);
      if (normalisee) setValue("immatriculation", normalisee);
    },
  });
  const vin = register("vin", {
    onBlur: (event: FocusEvent<HTMLInputElement>) => {
      const normalise = normaliserVin(event.target.value);
      if (normalise) setValue("vin", normalise);
    },
  });

  return (
    <form className="stack" noValidate onSubmit={handleSubmit(enregistrer)}>
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <div className="form-grid">
        <TextField label="Immatriculation" required mono autoComplete="off" autoCapitalize="characters" spellCheck={false} hint="Format AA-123-AA" error={errors.immatriculation?.message} {...immatriculation} />
        <TextField label="Marque" required error={errors.marque?.message} {...register("marque")} />
        <TextField label="Modèle" required error={errors.modele?.message} {...register("modele")} />
        <TextField label="Kilométrage" required mono inputMode="numeric" hint="En kilomètres" error={errors.kilometrage?.message} {...register("kilometrage")} />
        <TextField label="VIN" mono autoComplete="off" autoCapitalize="characters" spellCheck={false} hint="17 caractères, facultatif" error={errors.vin?.message} {...vin} />
        <TextField label="Mise en circulation" type="date" max={aujourdHui()} hint="Facultatif" error={errors.date_mise_en_circulation?.message} {...register("date_mise_en_circulation")} />
      </div>
      <div className="actions">
        <Button type="submit" variant="primary" loading={isSubmitting}>
          {mode === "creation" ? "Ajouter le véhicule" : "Enregistrer"}
        </Button>
        {onAnnuler ? <Button onClick={onAnnuler}>Annuler</Button> : null}
      </div>
    </form>
  );
}
