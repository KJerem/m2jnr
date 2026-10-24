"use client";

/** Onglet « Factures » : la numérotation et le PDF arrivent avec la story S4.3. */
export function ListeFactures({ page }: { page: number }) {
  void page;
  return <p className="panel empty">Aucune facture pour l&apos;instant.</p>;
}
