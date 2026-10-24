"use client";

import { forwardRef, useMemo } from "react";
import { SelectField, type SelectFieldProps } from "@/components/ui/Field";
import { nomComplet } from "@/lib/format";
import type { Vehicule } from "@/lib/vehicules";

interface Groupe {
  cle: number;
  proprietaire: string;
  vehicules: Vehicule[];
}

export function grouperParProprietaire(vehicules: Vehicule[]): Groupe[] {
  const groupes = new Map<number, Groupe>();
  for (const v of vehicules) {
    const groupe = groupes.get(v.proprietaire.id) ?? { cle: v.proprietaire.id, proprietaire: nomComplet(v.proprietaire), vehicules: [] };
    groupe.vehicules.push(v);
    groupes.set(v.proprietaire.id, groupe);
  }
  return [...groupes.values()];
}

export interface SelectVehiculeProps extends Omit<SelectFieldProps, "children"> {
  vehicules: Vehicule[];
}

/** Choix d'un véhicule, groupé par propriétaire : « GH-482-KL · Peugeot 308 SW ». */
export const SelectVehicule = forwardRef<HTMLSelectElement, SelectVehiculeProps>(function SelectVehicule({ vehicules, hint, ...rest }, ref) {
  const groupes = useMemo(() => grouperParProprietaire(vehicules), [vehicules]);
  return (
    <SelectField ref={ref} hint={vehicules.length === 0 ? "Aucun véhicule enregistré." : hint} {...rest}>
      <option value="">Choisir un véhicule</option>
      {groupes.map((g) => (
        <optgroup key={g.cle} label={g.proprietaire}>
          {g.vehicules.map((v) => (
            <option key={v.id} value={String(v.id)}>
              {v.immatriculation} · {v.marque} {v.modele}
            </option>
          ))}
        </optgroup>
      ))}
    </SelectField>
  );
});
