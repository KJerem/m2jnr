"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { rafraichirApresDevis } from "@/components/devis/donnees";
import { Button } from "@/components/ui/Button";
import { SelectField, TextField } from "@/components/ui/Field";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { ApiError, apiFetch } from "@/lib/api";
import {
  BADGE_PAIEMENT,
  LIBELLE_MODE,
  LIBELLE_PAIEMENT,
  lireMontant,
  messageTropPercu,
  MODES_PAIEMENT,
  montantSaisi,
  type FactureDetail,
  type ModePaiement,
  type StatutPaiement,
} from "@/lib/factures";
import { formatDateHeureOuAnnee, formatEuros } from "@/lib/format";

export const cleFacture = (factureId: number) => ["factures", "fiche", factureId] as const;

export interface PaiementSaisi {
  montant_centimes: number;
  mode: ModePaiement;
  recu_le?: string;
  reference?: string;
}

export function enregistrerPaiement(factureId: number, paiement: PaiementSaisi) {
  return apiFetch<FactureDetail>(`/factures/${factureId}/paiements`, { method: "POST", body: paiement });
}

/** Statut de paiement : badge (pastille + mot) et « En retard » en toutes lettres. */
export function BadgesPaiement({ statut, enRetard }: { statut: StatutPaiement; enRetard: boolean }) {
  return (
    <span className="row">
      <StatusBadge status={BADGE_PAIEMENT[statut]}>{LIBELLE_PAIEMENT[statut]}</StatusBadge>
      {enRetard ? <StatusBadge status="urgent">En retard</StatusBadge> : null}
    </span>
  );
}

type Champ = "montant" | "mode" | "recu_le" | "reference";
type Erreurs = Partial<Record<Champ, string>>;

const CHAMPS_API: Record<string, Champ> = { montant_centimes: "montant", mode: "mode", recu_le: "recu_le", reference: "reference" };

/**
 * Panneau « Paiements » de la facture (story S4.4) : paiements reçus, déjà payé, reste à
 * payer, statut ; formulaire « Enregistrer un paiement » (montant pré-rempli avec le reste)
 * tant que la facture n'est pas payée. Après un paiement, le focus revient sur le montant
 * (nouveau reste) ou, la facture payée, sur le reste à payer.
 */
export function PaiementsFacture({ facture }: { facture: FactureDetail }) {
  const queryClient = useQueryClient();
  const notifier = useToast();
  const [montant, setMontant] = useState(() => montantSaisi(facture.reste_centimes));
  const [mode, setMode] = useState<ModePaiement>("carte");
  const [recuLe, setRecuLe] = useState("");
  const [reference, setReference] = useState("");
  const [erreurs, setErreurs] = useState<Erreurs>({});
  const [erreurGenerale, setErreurGenerale] = useState<string | null>(null);
  const champMontant = useRef<HTMLInputElement>(null);
  const champMode = useRef<HTMLSelectElement>(null);
  const champDate = useRef<HTMLInputElement>(null);
  const champReference = useRef<HTMLInputElement>(null);
  const reste = useRef<HTMLParagraphElement>(null);
  const focaliser = useRef(false);
  const payee = facture.statut_paiement === "payee";

  const enregistrement = useMutation({
    mutationFn: (paiement: PaiementSaisi) => enregistrerPaiement(facture.id, paiement),
    onSuccess: (maj, paiement) => {
      queryClient.setQueryData(cleFacture(facture.id), maj);
      void rafraichirApresDevis(queryClient);
      setMontant(montantSaisi(maj.reste_centimes));
      setRecuLe("");
      setReference("");
      setErreurs({});
      setErreurGenerale(null);
      focaliser.current = true;
      notifier({
        type: "success",
        message:
          maj.statut_paiement === "payee"
            ? `Paiement de ${formatEuros(paiement.montant_centimes)} enregistré : facture ${maj.numero} payée.`
            : `Paiement de ${formatEuros(paiement.montant_centimes)} enregistré. Reste à payer : ${formatEuros(maj.reste_centimes)}.`,
      });
    },
    onError: (erreur) => {
      if (erreur instanceof ApiError && erreur.code === "trop_percu") {
        const resteServeur = typeof erreur.details.reste_centimes === "number" ? erreur.details.reste_centimes : facture.reste_centimes;
        afficherErreurs({ montant: messageTropPercu(resteServeur) });
        void queryClient.invalidateQueries({ queryKey: cleFacture(facture.id) });
        return;
      }
      if (erreur instanceof ApiError && erreur.code === "facture_payee") {
        setErreurGenerale(erreur.message);
        void queryClient.invalidateQueries({ queryKey: cleFacture(facture.id) });
        return;
      }
      if (erreur instanceof ApiError && Object.keys(erreur.champs).length > 0) {
        const parChamp: Erreurs = {};
        for (const [champ, message] of Object.entries(erreur.champs)) {
          const cible = CHAMPS_API[champ];
          if (cible) parChamp[cible] = message;
        }
        if (Object.keys(parChamp).length > 0) {
          afficherErreurs(parChamp);
          return;
        }
      }
      setErreurGenerale(erreur.message);
      notifier({ type: "error", message: erreur.message });
    },
  });

  // Après un paiement : montant (nouveau reste) ou, facture payée, reste à payer.
  useEffect(() => {
    if (!focaliser.current) return;
    focaliser.current = false;
    (payee ? reste.current : champMontant.current)?.focus();
  }, [payee, facture.reste_centimes, facture.paiements.length]);

  function afficherErreurs(parChamp: Erreurs) {
    setErreurs(parChamp);
    const ordre: [Champ, HTMLElement | null][] = [
      ["montant", champMontant.current],
      ["mode", champMode.current],
      ["recu_le", champDate.current],
      ["reference", champReference.current],
    ];
    ordre.find(([champ]) => parChamp[champ])?.[1]?.focus();
  }

  function envoyer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErreurGenerale(null);
    const lu = lireMontant(montant, facture.reste_centimes);
    if ("erreur" in lu) {
      afficherErreurs({ montant: lu.erreur });
      return;
    }
    setErreurs({});
    const paiement: PaiementSaisi = { montant_centimes: lu.centimes, mode };
    if (recuLe) paiement.recu_le = recuLe;
    if (reference.trim()) paiement.reference = reference.trim();
    enregistrement.mutate(paiement);
  }

  return (
    <section className="panel" aria-labelledby="titre-paiements">
      <div className="panel-head">
        <h2 id="titre-paiements">Paiements</h2>
        <BadgesPaiement statut={facture.statut_paiement} enRetard={facture.en_retard} />
      </div>
      <div className="panel-body stack">
        <div className="paiement-solde">
          <dl className="dl">
            <dt>Total TTC</dt>
            <dd className="num">{formatEuros(facture.totaux.total_ttc_centimes)}</dd>
            <dt>Déjà payé</dt>
            <dd className="num">{formatEuros(facture.deja_paye_centimes)}</dd>
          </dl>
          <div className="paiement-reste">
            <span className="label" aria-hidden="true">
              Reste à payer
            </span>
            <p ref={reste} tabIndex={-1} className="paiement-reste-montant num">
              <span className="sr-only">Reste à payer : </span>
              {formatEuros(facture.reste_centimes)}
            </p>
          </div>
        </div>

        {facture.paiements.length === 0 ? (
          <p className="muted">Aucun paiement enregistré.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <caption className="sr-only">Paiements reçus pour la facture {facture.numero}</caption>
              <thead>
                <tr>
                  <th scope="col">Reçu le</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Référence</th>
                  <th scope="col" className="right">
                    Montant
                  </th>
                </tr>
              </thead>
              <tbody>
                {facture.paiements.map((p) => (
                  <tr key={p.id}>
                    <td className="nowrap">{formatDateHeureOuAnnee(p.recu_le)}</td>
                    <td>{LIBELLE_MODE[p.mode]}</td>
                    <td className="mono">{p.reference ?? <span className="muted">—</span>}</td>
                    <td className="right num nowrap strong">{formatEuros(p.montant_centimes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {payee ? null : (
          <form className="stack paiement-form" onSubmit={envoyer} noValidate aria-labelledby="titre-nouveau-paiement">
            <h3 id="titre-nouveau-paiement">Enregistrer un paiement</h3>
            <div className="form-grid">
              <TextField
                ref={champMontant}
                label="Montant (€)"
                name="montant"
                inputMode="decimal"
                autoComplete="off"
                className="num"
                required
                value={montant}
                error={erreurs.montant}
                hint={`Reste à payer : ${formatEuros(facture.reste_centimes)}`}
                onChange={(e) => setMontant(e.target.value)}
              />
              <SelectField ref={champMode} label="Mode" name="mode" required value={mode} error={erreurs.mode} onChange={(e) => setMode(e.target.value as ModePaiement)}>
                {MODES_PAIEMENT.map((m) => (
                  <option key={m} value={m}>
                    {LIBELLE_MODE[m]}
                  </option>
                ))}
              </SelectField>
              <TextField
                ref={champDate}
                label="Reçu le"
                name="recu_le"
                type="datetime-local"
                value={recuLe}
                error={erreurs.recu_le}
                hint="Laissez vide pour maintenant."
                onChange={(e) => setRecuLe(e.target.value)}
              />
              <TextField
                ref={champReference}
                label="Référence"
                name="reference"
                maxLength={60}
                autoComplete="off"
                mono
                value={reference}
                error={erreurs.reference}
                hint="N° de chèque ou de virement, facultatif."
                onChange={(e) => setReference(e.target.value)}
              />
            </div>
            {erreurGenerale ? (
              <p className="callout callout-danger" role="alert">
                {erreurGenerale}
              </p>
            ) : null}
            <div className="actions">
              <Button type="submit" variant="primary" loading={enregistrement.isPending}>
                Enregistrer le paiement
              </Button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
