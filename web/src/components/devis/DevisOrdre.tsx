"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useFieldArray, useForm, useWatch, type Path } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { ApiError } from "@/lib/api";
import {
  calculerTotaux,
  CHAMP_API,
  devisSchema,
  formatQuantite,
  LIBELLE_TYPE_LIGNE,
  libelleTva,
  LIGNE_VIDE,
  ligneCalculable,
  LIGNES_MAX,
  TAUX_TVA_NORMAL_BP,
  totalLigne,
  versEntreeDevis,
  versFormulaireDevis,
  type DevisDetail,
  type DevisFormValues,
  type LigneCalcul,
  type LigneFormValues,
  type TotauxDevis,
} from "@/lib/devis";
import { formatEuros } from "@/lib/format";
import type { OrdreDetail } from "@/lib/ordres";
import { cleDevisOrdre, enregistrerDevis, rafraichirApresDevis, useDevisOrdre } from "./donnees";

export interface DevisOrdreProps {
  ordre: OrdreDetail;
  /** Prévenu quand l'édition s'ouvre ou se ferme (la fiche masque alors son bouton principal). */
  onEditionChange?: (edition: boolean) => void;
}

/** Section « Devis — pièces & main-d'œuvre » de la fiche d'un OT (gérant seulement). */
export function DevisOrdre({ ordre, onEditionChange }: DevisOrdreProps) {
  const queryClient = useQueryClient();
  const { data: devis, isPending, isError, error } = useDevisOrdre(ordre.id);
  const [edition, setEdition] = useState<{ ajouter: boolean } | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const boutonAjout = useRef<HTMLButtonElement>(null);

  function ouvrir(ajouter: boolean) {
    setMessage(null);
    setEdition({ ajouter });
    onEditionChange?.(true);
  }

  function fermer() {
    setEdition(null);
    onEditionChange?.(false);
  }

  const modifiable = devis !== undefined && !devis?.facture;

  return (
    <section className="panel" aria-labelledby="titre-devis">
      <div className="panel-head">
        <h2 id="titre-devis">Devis — pièces &amp; main-d&apos;œuvre</h2>
        {modifiable && !edition ? (
          <div className="actions">
            {devis ? (
              <Button variant="quiet" onClick={() => ouvrir(false)}>
                Modifier le devis
              </Button>
            ) : null}
            <Button ref={boutonAjout} variant="quiet" onClick={() => ouvrir(true)}>
              <Icon name="plus" />
              Ajouter une ligne
            </Button>
          </div>
        ) : null}
      </div>

      {isPending ? (
        <p className="empty" role="status">
          Chargement du devis…
        </p>
      ) : isError ? (
        <p className="empty danger-text" role="alert">
          {error.message}
        </p>
      ) : edition ? (
        <FormulaireDevis
          ordreId={ordre.id}
          devis={devis}
          ajouterLigne={edition.ajouter}
          onAnnuler={fermer}
          onSucces={(enregistre) => {
            queryClient.setQueryData(cleDevisOrdre(ordre.id), enregistre);
            void rafraichirApresDevis(queryClient);
            fermer();
            setMessage(`Devis enregistré : ${formatEuros(enregistre.totaux.total_ttc_centimes)} TTC.`);
          }}
        />
      ) : devis ? (
        <>
          <TableauDevis devis={devis} />
          <BlocTotaux totaux={devis.totaux} tauxBp={devis.taux_tva_bp} />
        </>
      ) : (
        <div className="panel-body">
          <p className="muted">Aucun devis pour cet ordre de travail.</p>
        </div>
      )}
      <p role="status" className={message ? "devis-message callout callout-success" : "sr-only"}>
        {message}
      </p>
    </section>
  );
}

/** Lignes du devis en lecture (référence en mono, quantité « 0,5 h » ou « 1 »). */
export function TableauDevis({ devis }: { devis: DevisDetail }) {
  return (
    <div className="table-wrap">
      <table className="table table-devis">
        <caption className="sr-only">Lignes du devis</caption>
        <thead>
          <tr>
            <th scope="col">Référence</th>
            <th scope="col">Désignation</th>
            <th scope="col" className="right">
              Qté
            </th>
            <th scope="col" className="right">
              PU HT
            </th>
            <th scope="col" className="right">
              Total HT
            </th>
          </tr>
        </thead>
        <tbody>
          {devis.lignes.map((ligne) => (
            <tr key={ligne.id}>
              <td className="mono nowrap">{ligne.reference ?? <span className="muted">—</span>}</td>
              <td>
                {ligne.designation}
                <span className="sr-only"> ({LIBELLE_TYPE_LIGNE[ligne.type]})</span>
              </td>
              <td className="right num nowrap">{formatQuantite(ligne.type, ligne.quantite)}</td>
              <td className="right num nowrap">{formatEuros(ligne.prix_unitaire_ht_centimes)}</td>
              <td className="right num nowrap strong">{formatEuros(ligne.total_ht_centimes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Totaux : main-d'œuvre, pièces, HT, TVA, TTC en grand. `vivant` annonce les recalculs. */
export function BlocTotaux({ totaux, tauxBp, vivant }: { totaux: TotauxDevis; tauxBp: number; vivant?: boolean }) {
  return (
    <div className="devis-totaux" aria-live={vivant ? "polite" : undefined}>
      <dl>
        <dt>Main-d&apos;œuvre HT</dt>
        <dd className="num">{formatEuros(totaux.main_oeuvre_ht_centimes)}</dd>
        <dt>Pièces HT</dt>
        <dd className="num">{formatEuros(totaux.pieces_ht_centimes)}</dd>
        <dt>Total HT</dt>
        <dd className="num">{formatEuros(totaux.total_ht_centimes)}</dd>
        <dt>{libelleTva(tauxBp)}</dt>
        <dd className="num">{formatEuros(totaux.total_tva_centimes)}</dd>
        <dt className="devis-ttc">Total TTC</dt>
        <dd className="devis-ttc num">{formatEuros(totaux.total_ttc_centimes)}</dd>
      </dl>
    </div>
  );
}

const CHAMPS_LIGNE = Object.keys(CHAMP_API) as (keyof LigneFormValues)[];

/** Rattache les erreurs de l'API (« lignes.1.quantite ») aux champs ; renvoie le message général sinon. */
function erreursApi(erreur: unknown, setError: (champ: Path<DevisFormValues>, message: string, focus: boolean) => void): string | null {
  if (!(erreur instanceof ApiError)) return "Enregistrement impossible. Réessayez.";
  let rattachees = 0;
  for (const [champ, message] of Object.entries(erreur.champs)) {
    if (champ === "lignes") {
      setError("lignes", message, false);
      rattachees += 1;
      continue;
    }
    const morceaux = /^lignes\.(\d+)\.(\w+)$/.exec(champ);
    const nom = CHAMPS_LIGNE.find((c) => CHAMP_API[c] === morceaux?.[2]);
    if (morceaux && nom) {
      setError(`lignes.${Number(morceaux[1])}.${nom}`, message, rattachees === 0);
      rattachees += 1;
    }
  }
  return rattachees > 0 ? null : erreur.message;
}

export interface FormulaireDevisProps {
  ordreId: number;
  devis: DevisDetail | null;
  ajouterLigne?: boolean;
  onAnnuler: () => void;
  onSucces: (devis: DevisDetail) => void;
}

/** Lignes dynamiques, totaux recalculés en direct (même arrondi que l'API), enregistrement. */
export function FormulaireDevis({ ordreId, devis, ajouterLigne, onAnnuler, onSucces }: FormulaireDevisProps) {
  const initiales = versFormulaireDevis(devis);
  if (ajouterLigne || initiales.lignes.length === 0) initiales.lignes.push({ ...LIGNE_VIDE });
  const {
    control,
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<DevisFormValues>({ resolver: zodResolver(devisSchema), defaultValues: initiales, mode: "onTouched" });
  const { fields, append, remove } = useFieldArray({ control, name: "lignes", keyName: "cle" });
  const lignes = useWatch({ control, name: "lignes" }) ?? [];
  const boutonAjout = useRef<HTMLButtonElement>(null);
  const [general, setGeneral] = useState<string | null>(null);
  const tauxBp = devis?.taux_tva_bp ?? TAUX_TVA_NORMAL_BP;
  const calculables = lignes.map(ligneCalculable);
  const totaux = calculerTotaux(
    calculables.filter((l): l is LigneCalcul => l !== null),
    tauxBp,
  );

  const enregistrement = useMutation({
    mutationFn: (valeurs: DevisFormValues) => enregistrerDevis(ordreId, devis, versEntreeDevis(valeurs)),
    onSuccess: onSucces,
    onError: (erreur) => setGeneral(erreursApi(erreur, (champ, message, focus) => setError(champ, { type: "server", message }, { shouldFocus: focus }))),
  });

  return (
    <form
      className="devis-form"
      noValidate
      onSubmit={handleSubmit((valeurs) => {
        setGeneral(null);
        enregistrement.mutate(valeurs);
      })}
    >
      <ol className="devis-lignes">
        {fields.map((field, index) => {
          const numero = index + 1;
          const erreurs = errors.lignes?.[index];
          const type = lignes[index]?.type ?? field.type;
          const calcul = calculables[index];
          return (
            <li key={field.cle}>
              <fieldset className="devis-ligne">
                <legend className="label">Ligne {numero}</legend>
                <SelectField label="Type" className="devis-type" error={erreurs?.type?.message} {...register(`lignes.${index}.type`)}>
                  <option value="main_oeuvre">{LIBELLE_TYPE_LIGNE.main_oeuvre}</option>
                  <option value="piece">{LIBELLE_TYPE_LIGNE.piece}</option>
                </SelectField>
                <TextField label="Référence" mono className="devis-ref" autoComplete="off" maxLength={40} error={erreurs?.reference?.message} {...register(`lignes.${index}.reference`)} />
                <TextField label="Désignation" required className="devis-desig" autoComplete="off" error={erreurs?.designation?.message} {...register(`lignes.${index}.designation`)} />
                <TextField
                  label={type === "main_oeuvre" ? "Heures" : "Quantité"}
                  required
                  className="devis-qte"
                  inputMode="decimal"
                  autoComplete="off"
                  error={erreurs?.quantite?.message}
                  {...register(`lignes.${index}.quantite`)}
                />
                <TextField label="PU HT (€)" required className="devis-pu" inputMode="decimal" autoComplete="off" error={erreurs?.prix?.message} {...register(`lignes.${index}.prix`)} />
                <div className="devis-total-ligne">
                  <span className="et-field-label" id={`devis-total-${field.cle}`}>
                    Total HT
                  </span>
                  <output className="num strong" aria-labelledby={`devis-total-${field.cle}`}>
                    {calcul ? formatEuros(totalLigne(calcul.quantiteCentiemes, calcul.prixUnitaireCentimes)) : "—"}
                  </output>
                </div>
                <Button
                  variant="quiet"
                  className="devis-retirer"
                  aria-label={`Retirer la ligne ${numero}`}
                  onClick={() => {
                    remove(index);
                    boutonAjout.current?.focus();
                  }}
                >
                  Retirer
                </Button>
              </fieldset>
            </li>
          );
        })}
      </ol>
      {fields.length === 0 ? <p className="muted devis-vide">Aucune ligne : ajoutez une pièce ou de la main-d&apos;œuvre.</p> : null}
      {errors.lignes?.message || errors.lignes?.root?.message ? (
        <p className="danger-text devis-vide" role="alert">
          {errors.lignes.message ?? errors.lignes.root?.message}
        </p>
      ) : null}
      <div className="devis-ajout">
        <Button ref={boutonAjout} variant="quiet" onClick={() => append({ ...LIGNE_VIDE })} disabled={fields.length >= LIGNES_MAX}>
          <Icon name="plus" />
          Ajouter une ligne
        </Button>
      </div>
      <BlocTotaux totaux={totaux} tauxBp={tauxBp} vivant />
      {general ? (
        <p className="callout callout-danger devis-vide" role="alert">
          {general}
        </p>
      ) : null}
      <div className="devis-actions">
        <Button onClick={onAnnuler} disabled={enregistrement.isPending}>
          Annuler
        </Button>
        <Button type="submit" variant="primary" loading={enregistrement.isPending}>
          Enregistrer le devis
        </Button>
      </div>
    </form>
  );
}
