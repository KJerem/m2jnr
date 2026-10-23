export interface PlateProps {
  /** Immatriculation formatée, par exemple « GH-482-KL ». */
  number: string;
  /** Lettre pays de la bande européenne. */
  country?: string;
  size?: "md" | "lg";
}

/** Plaque d'immatriculation : le véhicule se montre par sa plaque, jamais par un pictogramme. */
export function Plate({ number, country = "F", size = "md" }: PlateProps) {
  return (
    <span className={`et-plate${size === "lg" ? " et-plate-lg" : ""}`} role="img" aria-label={`Immatriculation ${number}`}>
      <span className="et-plate-band" aria-hidden="true">
        {country}
      </span>
      <span className="et-plate-num" aria-hidden="true">
        {number}
      </span>
    </span>
  );
}
