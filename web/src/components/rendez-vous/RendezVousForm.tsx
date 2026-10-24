"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { SelectVehicule } from "@/components/vehicules/SelectVehicule";
import { ApiError } from "@/lib/api";
import { appliquerErreursApi } from "@/lib/formulaires";
import { formatDureeHM } from "@/lib/ordres";
import {
  creerSchemaRendezVous,
  DUREES_RDV,
  RENDEZ_VOUS_VIDE,
  versEntreeRendezVous,
  type Pont,
  type RendezVous,
  type RendezVousEntree,
  type RendezVousFormValues,
} from "@/lib/rendezvous";
import { aujourdHui, type Vehicule } from "@/lib/vehicules";

const CHAMPS = ["vehicule_id", "pont_id", "jour", "heure", "duree_minutes", "motif"] as const;

export interface RendezVousFormProps {
  vehicules: Vehicule[];
  ponts: Pont[];
  envoyer: (entree: RendezVousEntree) => Promise<RendezVous>;
  onSucces: (rdv: RendezVous) => void;
  /** Horloge injectable pour les tests (refus d'un créneau passé). */
  maintenant?: () => Date;
}

/** Prise de rendez-vous : véhicule, pont, jour, heure (Paris), durée et motif, tous obligatoires. */
export function RendezVousForm({ vehicules, ponts, envoyer, onSucces, maintenant }: RendezVousFormProps) {
  const schema = useMemo(() => creerSchemaRendezVous(maintenant), [maintenant]);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<RendezVousFormValues>({ resolver: zodResolver(schema), defaultValues: RENDEZ_VOUS_VIDE });
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);

  async function enregistrer(valeurs: RendezVousFormValues) {
    setErreurGenerale(null);
    try {
      const rdv = await envoyer(versEntreeRendezVous(valeurs));
      // On garde le pont et le jour : on enchaîne souvent plusieurs rendez-vous.
      reset({ ...RENDEZ_VOUS_VIDE, pont_id: getValues("pont_id"), jour: getValues("jour") });
      onSucces(rdv);
    } catch (erreur) {
      if (erreur instanceof ApiError && erreur.code === "creneau_occupe") {
        setError("heure", { type: "server", message: erreur.message }, { shouldFocus: true });
        return;
      }
      if (erreur instanceof ApiError && erreur.champs.debut) {
        setError("jour", { type: "server", message: erreur.champs.debut }, { shouldFocus: true });
        return;
      }
      setErreurGenerale(appliquerErreursApi(erreur, CHAMPS, setError));
    }
  }

  return (
    <form className="stack" noValidate onSubmit={handleSubmit(enregistrer)}>
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <div className="form-grid">
        <SelectVehicule label="Véhicule" required vehicules={vehicules} error={errors.vehicule_id?.message} {...register("vehicule_id")} />
        <SelectField label="Pont" required error={errors.pont_id?.message} {...register("pont_id")}>
          <option value="">Choisir un pont</option>
          {ponts.map((p) => (
            <option key={p.id} value={String(p.id)}>
              {p.nom}
            </option>
          ))}
        </SelectField>
        <TextField label="Jour" type="date" required min={aujourdHui(maintenant?.())} error={errors.jour?.message} {...register("jour")} />
        <TextField label="Heure" type="time" required step={900} hint="Heure de Paris" error={errors.heure?.message} {...register("heure")} />
        <SelectField label="Durée" required error={errors.duree_minutes?.message} {...register("duree_minutes")}>
          {DUREES_RDV.map((m) => (
            <option key={m} value={String(m)}>
              {formatDureeHM(m)}
            </option>
          ))}
        </SelectField>
      </div>
      <TextField label="Motif" required autoComplete="off" hint="Par exemple : révision des 90 000 km" error={errors.motif?.message} {...register("motif")} />
      <div className="actions">
        <Button type="submit" variant="primary" loading={isSubmitting}>
          Enregistrer le rendez-vous
        </Button>
      </div>
    </form>
  );
}
