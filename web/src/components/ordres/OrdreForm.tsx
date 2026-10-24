"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState } from "react";
import { useForm, useWatch, type Path } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { SelectField, TextAreaField, TextField } from "@/components/ui/Field";
import { appliquerErreursApi } from "@/lib/formulaires";
import { formatKm, nomComplet } from "@/lib/format";
import {
  MESSAGE_VEHICULE_OBLIGATOIRE,
  ordreSchema,
  versEntreeOrdre,
  type OrdreDetail,
  type OrdreEntree,
  type OrdreFormValues,
  type UtilisateurResume,
} from "@/lib/ordres";
import type { Vehicule } from "@/lib/vehicules";
import { TachesEditeur } from "./TachesEditeur";

const CHAMPS_FIXES = ["vehicule_id", "demande_client", "diagnostic", "prioritaire", "kilometrage_entree", "restitution_prevue", "mecanicien_id"] as const;

export interface OrdreFormProps {
  mode: "creation" | "modification";
  valeursInitiales: OrdreFormValues;
  /** Véhicules proposés (création), triés par propriétaire. */
  vehicules: Vehicule[];
  mecaniciens: UtilisateurResume[];
  envoyer: (entree: OrdreEntree) => Promise<OrdreDetail>;
  onSucces: (ordre: OrdreDetail) => void;
  onAnnuler?: () => void;
}

interface Groupe {
  proprietaire: string;
  vehicules: Vehicule[];
}

function grouperParProprietaire(vehicules: Vehicule[]): Groupe[] {
  const groupes = new Map<number, Groupe>();
  for (const v of vehicules) {
    const groupe = groupes.get(v.proprietaire.id) ?? { proprietaire: nomComplet(v.proprietaire), vehicules: [] };
    groupe.vehicules.push(v);
    groupes.set(v.proprietaire.id, groupe);
  }
  return [...groupes.values()];
}

export function OrdreForm({ mode, valeursInitiales, vehicules, mecaniciens, envoyer, onSucces, onAnnuler }: OrdreFormProps) {
  const {
    register,
    control,
    handleSubmit,
    setError,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<OrdreFormValues>({ resolver: zodResolver(ordreSchema), defaultValues: valeursInitiales });
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);
  const groupes = useMemo(() => grouperParProprietaire(vehicules), [vehicules]);
  const vehiculeId = useWatch({ control, name: "vehicule_id" });
  const vehicule = vehicules.find((v) => String(v.id) === vehiculeId);
  const creation = mode === "creation";

  async function enregistrer(valeurs: OrdreFormValues) {
    setErreurGenerale(null);
    if (creation && !valeurs.vehicule_id) {
      setError("vehicule_id", { type: "required", message: MESSAGE_VEHICULE_OBLIGATOIRE }, { shouldFocus: true });
      return;
    }
    const entree = versEntreeOrdre(valeurs);
    if (creation && vehicule && entree.kilometrage_entree != null && entree.kilometrage_entree < vehicule.kilometrage) {
      setError(
        "kilometrage_entree",
        { type: "min", message: `Le kilométrage d'entrée ne peut pas être inférieur à celui du véhicule (${formatKm(vehicule.kilometrage)}).` },
        { shouldFocus: true },
      );
      return;
    }
    if (!creation) {
      delete entree.vehicule_id;
      delete entree.kilometrage_entree;
    }
    try {
      onSucces(await envoyer(entree));
    } catch (erreur) {
      const champsTaches = getValues("taches").flatMap((_, i) => [`taches.${i}.libelle`, `taches.${i}.duree_prevue_minutes`] as Path<OrdreFormValues>[]);
      setErreurGenerale(appliquerErreursApi(erreur, [...CHAMPS_FIXES, ...champsTaches], setError));
    }
  }

  return (
    <form className="stack" noValidate onSubmit={handleSubmit(enregistrer)}>
      <div role="alert" className={erreurGenerale ? "callout callout-danger" : undefined}>
        {erreurGenerale}
      </div>
      <div className="form-grid">
        {creation ? (
          <SelectField label="Véhicule" required error={errors.vehicule_id?.message} hint={vehicules.length === 0 ? "Aucun véhicule enregistré." : undefined} {...register("vehicule_id")}>
            <option value="">Choisir un véhicule</option>
            {groupes.map((g) => (
              <optgroup key={g.proprietaire + g.vehicules[0]?.id} label={g.proprietaire}>
                {g.vehicules.map((v) => (
                  <option key={v.id} value={String(v.id)}>
                    {v.immatriculation} · {v.marque} {v.modele}
                  </option>
                ))}
              </optgroup>
            ))}
          </SelectField>
        ) : null}
        <SelectField label="Mécanicien" hint="Facultatif" error={errors.mecanicien_id?.message} {...register("mecanicien_id")}>
          <option value="">Non affecté</option>
          {mecaniciens.map((m) => (
            <option key={m.id} value={String(m.id)}>
              {m.nom}
            </option>
          ))}
        </SelectField>
        <TextField label="Restitution prévue" type="datetime-local" hint="Heure de Paris, facultatif" error={errors.restitution_prevue?.message} {...register("restitution_prevue")} />
        {creation ? (
          <TextField
            label="Kilométrage d'entrée"
            mono
            inputMode="numeric"
            autoComplete="off"
            hint={vehicule ? `Dernier relevé : ${formatKm(vehicule.kilometrage)}` : "Facultatif"}
            error={errors.kilometrage_entree?.message}
            {...register("kilometrage_entree")}
          />
        ) : null}
      </div>
      <TextAreaField label="Demande du client" required rows={3} error={errors.demande_client?.message} {...register("demande_client")} />
      <TextAreaField label="Diagnostic" hint="Facultatif" rows={3} error={errors.diagnostic?.message} {...register("diagnostic")} />
      <label className="et-check">
        <input type="checkbox" {...register("prioritaire")} />
        <span>Urgent : client sur place ou véhicule à rendre en priorité</span>
      </label>
      <TachesEditeur control={control} register={register} errors={errors} />
      <div className="actions">
        <Button type="submit" variant="primary" loading={isSubmitting}>
          {creation ? "Ouvrir l'ordre de travail" : "Enregistrer"}
        </Button>
        {onAnnuler ? <Button onClick={onAnnuler}>Annuler</Button> : null}
      </div>
    </form>
  );
}
