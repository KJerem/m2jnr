"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState, type RefObject } from "react";
import { useFieldArray, useForm, useWatch, type Path } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { ApiError, apiFetch } from "@/lib/api";
import {
  AIDE_STATUT_DEVIS,
  BADGE_DEVIS,
  calculerTotaux,
  CHAMP_API,
  devisModifiable,
  devisSchema,
  formatQuantite,
  LIBELLE_DEVIS,
  LIBELLE_TYPE_LIGNE,
  libelleTva,
  LIGNE_VIDE,
  ligneCalculable,
  LIGNES_MAX,
  phraseStatutDevis,
  TAUX_TVA_NORMAL_BP,
  totalLigne,
  versEntreeDevis,
  versFormulaireDevis,
  type DevisDetail,
  type DevisFormValues,
  type LigneCalcul,
  type LigneFormValues,
  type StatutDevis,
  type TotauxDevis,
} from "@/lib/devis";
import { factureDisponible, lienPdf, MESSAGE_FACTURE_INDISPONIBLE, numeroAVenir, type FactureDetail } from "@/lib/factures";
import { formatEuros } from "@/lib/format";
import type { OrdreDetail } from "@/lib/ordres";
import type { StatutOT } from "@/lib/statuts";
import { changerStatutDevis, cleDevisOrdre, enregistrerDevis, rafraichirApresDevis, useDevisOrdre } from "./donnees";

export interface DevisOrdreProps {
  ordre: OrdreDetail;
  /** Prévenu quand l'édition s'ouvre ou se ferme (la fiche masque alors son bouton principal). */
  onEditionChange?: (edition: boolean) => void;
}

interface Edition {
  ajouter: boolean;
  /** Nouveau devis après un refus : lignes du devis refusé reprises, enregistrées en création. */
  remplace?: DevisDetail;
}

/** Section « Devis — pièces & main-d'œuvre » de la fiche d'un OT (gérant seulement). */
export function DevisOrdre({ ordre, onEditionChange }: DevisOrdreProps) {
  const queryClient = useQueryClient();
  const { data: devis, isPending, isError, error } = useDevisOrdre(ordre.id);
  const [edition, setEdition] = useState<Edition | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const boutonAjout = useRef<HTMLButtonElement>(null);
  const boutonModifier = useRef<HTMLButtonElement>(null);
  const boutonFacture = useRef<HTMLButtonElement>(null);
  const titre = useRef<HTMLHeadingElement>(null);
  // Le formulaire démonte le bouton qui avait le focus (Annuler, Enregistrer) : sans relais,
  // le focus tombait sur <body> et l'utilisateur au clavier repartait du haut de la page.
  const rendreFocus = useRef(false);

  function ouvrir(ouverture: Edition) {
    setMessage(null);
    setEdition(ouverture);
    onEditionChange?.(true);
  }

  function fermer() {
    rendreFocus.current = true;
    setEdition(null);
    onEditionChange?.(false);
  }

  useEffect(() => {
    if (edition || !rendreFocus.current) return;
    rendreFocus.current = false;
    (boutonModifier.current ?? boutonAjout.current ?? titre.current)?.focus();
  }, [edition]);

  // Story S4.2 : seul un brouillon se modifie ; sans devis, on peut en créer un.
  const modifiable = devis !== undefined && (devis === null || devisModifiable(devis));

  return (
    <section className="panel" aria-labelledby="titre-devis">
      <div className="panel-head">
        <div className="row">
          <h2 id="titre-devis" ref={titre} tabIndex={-1}>
            Devis — pièces &amp; main-d&apos;œuvre
          </h2>
          {devis ? (
            <StatusBadge status={BADGE_DEVIS[devis.statut]}>
              <span className="sr-only">Statut du devis : </span>
              {LIBELLE_DEVIS[devis.statut]}
            </StatusBadge>
          ) : null}
        </div>
        {modifiable && !edition ? (
          <div className="actions">
            {devis ? (
              <Button ref={boutonModifier} variant="quiet" onClick={() => ouvrir({ ajouter: false })}>
                Modifier le devis
              </Button>
            ) : null}
            <Button ref={boutonAjout} variant="quiet" onClick={() => ouvrir({ ajouter: true })}>
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
          devis={edition.remplace ? null : devis}
          remplace={edition.remplace}
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
          <ActionsStatutDevis
            devis={devis}
            boutonFacture={boutonFacture}
            onChange={(maj) => {
              setMessage(null);
              queryClient.setQueryData(cleDevisOrdre(ordre.id), maj);
              void rafraichirApresDevis(queryClient);
            }}
            onNouveau={() => ouvrir({ ajouter: false, remplace: devis })}
          />
          {devis.statut !== "refuse" ? (
            <PiedFacturation
              statut={ordre.statut}
              devis={devis}
              boutonRef={boutonFacture}
              onEmise={(facture) => {
                queryClient.setQueryData(cleDevisOrdre(ordre.id), { ...devis, facture: { id: facture.id, numero: facture.numero } });
                void rafraichirApresDevis(queryClient);
                setMessage(`Facture ${facture.numero} établie : ${formatEuros(facture.totaux.total_ttc_centimes)} TTC.`);
              }}
            />
          ) : null}
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

const SUCCES_STATUT: Record<Exclude<StatutDevis, "brouillon">, string> = {
  envoye: "Devis marqué comme envoyé au client.",
  accepte: "Devis accepté par le client.",
  refuse: "Devis refusé par le client.",
};

export interface ActionsStatutDevisProps {
  devis: DevisDetail;
  onChange: (devis: DevisDetail) => void;
  /** « Nouveau devis » après un refus. */
  onNouveau: () => void;
  /** « Générer la facture » : reçoit le focus après l'acceptation s'il est actif. */
  boutonFacture?: RefObject<HTMLButtonElement | null>;
}

/**
 * Statut du devis (story S4.2) : phrase d'état et action suivante. Brouillon : « Marquer
 * comme envoyé au client » (l'application n'envoie rien elle-même) ; envoyé : « Accepté par
 * le client » ou « Refusé par le client » (refus confirmé) ; refusé : « Nouveau devis ».
 * Après chaque action, le focus va sur l'action suivante, à défaut sur la phrase d'état.
 */
export function ActionsStatutDevis({ devis, onChange, onNouveau, boutonFacture }: ActionsStatutDevisProps) {
  const notifier = useToast();
  const [confirmerRefus, setConfirmerRefus] = useState(false);
  const phrase = useRef<HTMLParagraphElement>(null);
  const boutonAccepter = useRef<HTMLButtonElement>(null);
  const boutonRefuser = useRef<HTMLButtonElement>(null);
  const boutonNouveau = useRef<HTMLButtonElement>(null);
  const focaliser = useRef(false);
  const changement = useMutation({
    mutationFn: (nouveau: StatutDevis) => changerStatutDevis(devis.id, nouveau),
    onSuccess: (maj) => {
      focaliser.current = true;
      setConfirmerRefus(false);
      if (maj.statut !== "brouillon") notifier({ type: "success", message: SUCCES_STATUT[maj.statut] });
      onChange(maj);
    },
    onError: (erreur) => {
      setConfirmerRefus(false);
      notifier({ type: "error", message: erreur.message });
    },
  });

  useEffect(() => {
    if (!focaliser.current) return;
    focaliser.current = false;
    const facture = boutonFacture?.current;
    const cible =
      devis.statut === "envoye"
        ? boutonAccepter.current
        : devis.statut === "refuse"
          ? boutonNouveau.current
          : devis.statut === "accepte" && facture && !facture.disabled
            ? facture
            : null;
    (cible ?? phrase.current)?.focus();
  }, [devis.statut, boutonFacture]);

  const idPhrase = `devis-statut-${devis.id}`;
  const aide = devis.facture ? null : AIDE_STATUT_DEVIS[devis.statut];
  return (
    <div className="devis-statut">
      <div className="stack-xs">
        <p ref={phrase} tabIndex={-1} id={idPhrase} className="strong">
          {phraseStatutDevis(devis)}
        </p>
        {aide ? <p className="caption">{aide}</p> : null}
      </div>
      {devis.facture ? null : (
        <div className="actions">
          {devis.statut === "brouillon" ? (
            <Button loading={changement.isPending} onClick={() => changement.mutate("envoye")}>
              Marquer comme envoyé au client
            </Button>
          ) : null}
          {devis.statut === "envoye" ? (
            <>
              <Button ref={boutonAccepter} loading={changement.isPending && changement.variables === "accepte"} disabled={changement.isPending} onClick={() => changement.mutate("accepte")}>
                Accepté par le client
              </Button>
              <Button
                ref={boutonRefuser}
                variant="danger"
                disabled={changement.isPending}
                onClick={() => {
                  changement.reset();
                  setConfirmerRefus(true);
                }}
              >
                Refusé par le client
              </Button>
            </>
          ) : null}
          {devis.statut === "refuse" ? (
            <Button ref={boutonNouveau} onClick={onNouveau}>
              <Icon name="plus" />
              Nouveau devis
            </Button>
          ) : null}
        </div>
      )}
      {confirmerRefus ? (
        <Modal
          titre="Refusé par le client"
          onClose={() => setConfirmerRefus(false)}
          retourFocus={boutonRefuser}
          actions={
            <>
              <Button onClick={() => setConfirmerRefus(false)} disabled={changement.isPending}>
                Annuler
              </Button>
              <Button variant="danger" loading={changement.isPending} onClick={() => changement.mutate("refuse")}>
                Confirmer le refus
              </Button>
            </>
          }
        >
          <p>
            Le devis de <span className="strong">{formatEuros(devis.totaux.total_ttc_centimes)} TTC</span> sera marqué refusé par le client.
          </p>
          <p>Cette décision est définitive ; vous pourrez ensuite établir un nouveau devis pour cette intervention.</p>
        </Modal>
      ) : null}
    </div>
  );
}

export interface PiedFacturationProps {
  statut: StatutOT;
  devis: DevisDetail;
  onEmise: (facture: FactureDetail) => void;
  /** Référence du bouton « Générer la facture » (focus après l'acceptation du devis). */
  boutonRef?: RefObject<HTMLButtonElement | null>;
}

/**
 * Facturation du devis : « Générer la facture » (actif quand le devis est accepté et
 * l'intervention « Prêt » ou « Livré », confirmation obligatoire), puis lien vers la facture
 * et son PDF.
 */
export function PiedFacturation({ statut, devis, onEmise, boutonRef }: PiedFacturationProps) {
  const [confirmation, setConfirmation] = useState(false);
  const boutonInterne = useRef<HTMLButtonElement>(null);
  const bouton = boutonRef ?? boutonInterne;
  const lienPdfFacture = useRef<HTMLAnchorElement>(null);
  // Après l'émission, le bouton « Générer la facture » disparaît avec la fenêtre : le focus
  // va sur « Télécharger le PDF », action suivante du nouvel état.
  const focaliserFacture = useRef(false);
  const emission = useMutation({
    mutationFn: () => apiFetch<FactureDetail>(`/devis/${devis.id}/facture`, { method: "POST" }),
    onSuccess: (facture) => {
      focaliserFacture.current = true;
      setConfirmation(false);
      onEmise(facture);
    },
  });
  const factureId = devis.facture?.id;

  useEffect(() => {
    if (factureId === undefined || !focaliserFacture.current) return;
    focaliserFacture.current = false;
    lienPdfFacture.current?.focus();
  }, [factureId]);

  if (devis.facture) {
    const { id, numero } = devis.facture;
    return (
      <div className="devis-pied">
        <p id={`facture-${id}`}>
          Facture <span className="mono strong">{numero}</span>
          <span className="caption"> · le devis ne peut plus être modifié</span>
        </p>
        <div className="actions">
          <a ref={lienPdfFacture} className="et-btn et-btn-secondary" href={lienPdf(id)} download aria-describedby={`facture-${id}`}>
            Télécharger le PDF
          </a>
          <Link href={`/factures/${id}`} className="et-btn et-btn-quiet">
            Voir la facture
          </Link>
        </div>
      </div>
    );
  }

  const possible = factureDisponible(statut, devis.statut);
  return (
    <div className="devis-pied">
      <p className="caption" id="facture-aide">
        {possible ? "La facture reprend exactement ce devis." : MESSAGE_FACTURE_INDISPONIBLE}
      </p>
      <Button
        ref={bouton}
        disabled={!possible}
        aria-describedby="facture-aide"
        onClick={() => {
          emission.reset();
          setConfirmation(true);
        }}
      >
        Générer la facture
      </Button>
      {confirmation ? (
        <Modal
          titre="Générer la facture"
          onClose={() => setConfirmation(false)}
          retourFocus={bouton}
          actions={
            <>
              <Button onClick={() => setConfirmation(false)} disabled={emission.isPending}>
                Annuler
              </Button>
              <Button variant="primary" loading={emission.isPending} onClick={() => emission.mutate()}>
                Générer la facture
              </Button>
            </>
          }
        >
          <p>La facture {numeroAVenir()} sera numérotée et ne pourra plus être modifiée.</p>
          <p>
            Montant : <span className="strong">{formatEuros(devis.totaux.total_ttc_centimes)} TTC</span>
          </p>
          {emission.isError ? (
            <p className="callout callout-danger" role="alert">
              {emission.error.message}
            </p>
          ) : null}
        </Modal>
      ) : null}
    </div>
  );
}

/** Lignes du devis en lecture (référence en mono, quantité « 0,5 h » ou « 1 »). */
export function TableauDevis({ devis, legende = "Lignes du devis" }: { devis: Pick<DevisDetail, "lignes">; legende?: string }) {
  return (
    <div className="table-wrap">
      <table className="table table-devis">
        <caption className="sr-only">{legende}</caption>
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
  /** Devis refusé dont les lignes servent de point de départ à un nouveau devis (création). */
  remplace?: DevisDetail;
  ajouterLigne?: boolean;
  onAnnuler: () => void;
  onSucces: (devis: DevisDetail) => void;
}

/** Lignes dynamiques, totaux recalculés en direct (même arrondi que l'API), enregistrement. */
export function FormulaireDevis({ ordreId, devis, remplace, ajouterLigne, onAnnuler, onSucces }: FormulaireDevisProps) {
  const initiales = versFormulaireDevis(devis ?? remplace ?? null);
  if (ajouterLigne || initiales.lignes.length === 0) initiales.lignes.push({ ...LIGNE_VIDE });
  // Ligne qui reçoit le focus à l'ouverture : la ligne ajoutée, sinon la première.
  const ligneInitiale = ajouterLigne ? initiales.lignes.length - 1 : 0;
  const {
    control,
    register,
    handleSubmit,
    setError,
    setFocus,
    formState: { errors },
  } = useForm<DevisFormValues>({ resolver: zodResolver(devisSchema), defaultValues: initiales, mode: "onTouched" });
  const { fields, append, remove } = useFieldArray({ control, name: "lignes", keyName: "cle" });
  const lignes = useWatch({ control, name: "lignes" }) ?? [];
  const boutonAjout = useRef<HTMLButtonElement>(null);
  const [general, setGeneral] = useState<string | null>(null);
  const tauxBp = devis?.taux_tva_bp ?? remplace?.taux_tva_bp ?? TAUX_TVA_NORMAL_BP;
  const calculables = lignes.map(ligneCalculable);
  const totaux = calculerTotaux(
    calculables.filter((l): l is LigneCalcul => l !== null),
    tauxBp,
  );

  useEffect(() => {
    setFocus(`lignes.${ligneInitiale}.type`);
  }, [setFocus, ligneInitiale]);

  const enregistrement = useMutation({
    mutationFn: (valeurs: DevisFormValues) => enregistrerDevis(ordreId, devis, versEntreeDevis(valeurs)),
    onSuccess: (enregistre) => onSucces(enregistre),
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
