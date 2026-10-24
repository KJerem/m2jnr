"use client";

import { useRef } from "react";
import { useFieldArray, useWatch, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { formatDureeHeures } from "@/lib/format";
import { DUREES_TACHE, formatDureeHM, TACHE_VIDE, TACHES_MAX, type OrdreFormValues } from "@/lib/ordres";

export interface TachesEditeurProps {
  control: Control<OrdreFormValues>;
  register: UseFormRegister<OrdreFormValues>;
  errors: FieldErrors<OrdreFormValues>;
}

function optionsDuree(actuelle: string) {
  const valeur = Number(actuelle);
  const liste = DUREES_TACHE.includes(valeur) || !Number.isInteger(valeur) || valeur < 1 ? DUREES_TACHE : [...DUREES_TACHE, valeur].sort((a, b) => a - b);
  return liste.map((m) => (
    <option key={m} value={String(m)}>
      {formatDureeHeures(m)}
    </option>
  ));
}

/** Lignes de tâches dynamiques : libellé et durée prévue, ajout et retrait au clavier. */
export function TachesEditeur({ control, register, errors }: TachesEditeurProps) {
  const { fields, append, remove } = useFieldArray({ control, name: "taches", keyName: "cle" });
  const taches = useWatch({ control, name: "taches" }) ?? [];
  const boutonAjout = useRef<HTMLButtonElement>(null);
  const totalMinutes = taches.reduce((somme, t) => somme + (Number(t?.duree_prevue_minutes) || 0), 0);

  return (
    <fieldset className="taches-editeur">
      <legend className="label">Travaux à réaliser</legend>
      {fields.length === 0 ? (
        <p className="muted">Aucune tâche prévue pour l&apos;instant.</p>
      ) : (
        <ol className="tache-lignes">
          {fields.map((field, index) => {
            const numero = index + 1;
            const erreurs = errors.taches?.[index];
            return (
              <li key={field.cle} className="tache-ligne">
                <span className="tache-num mono" aria-hidden="true">
                  {numero}
                </span>
                <TextField label={`Tâche ${numero}`} required autoComplete="off" error={erreurs?.libelle?.message} {...register(`taches.${index}.libelle`)} />
                <SelectField label={`Durée de la tâche ${numero}`} error={erreurs?.duree_prevue_minutes?.message} {...register(`taches.${index}.duree_prevue_minutes`)}>
                  {optionsDuree(taches[index]?.duree_prevue_minutes ?? "")}
                </SelectField>
                <Button
                  variant="quiet"
                  className="tache-retirer"
                  aria-label={`Retirer la tâche ${numero}`}
                  onClick={() => {
                    remove(index);
                    boutonAjout.current?.focus();
                  }}
                >
                  Retirer
                </Button>
              </li>
            );
          })}
        </ol>
      )}
      {errors.taches?.message ? (
        <p className="danger-text" role="alert">
          {errors.taches.message}
        </p>
      ) : null}
      <div className="row">
        <Button ref={boutonAjout} onClick={() => append({ ...TACHE_VIDE })} disabled={fields.length >= TACHES_MAX}>
          <Icon name="plus" />
          Ajouter une tâche
        </Button>
        {fields.length > 0 ? (
          <span className="caption" aria-live="polite">
            {fields.length} {fields.length > 1 ? "tâches" : "tâche"} · {formatDureeHM(totalMinutes)} prévues
          </span>
        ) : null}
      </div>
    </fieldset>
  );
}
