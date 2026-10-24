import Link from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode, Ref } from "react";

type Variant = "primary" | "secondary" | "quiet" | "danger";
type Size = "sm" | "md" | "lg";

function classes(variant: Variant, size: Size, block?: boolean, extra?: string) {
  return ["et-btn", `et-btn-${variant}`, size !== "md" && `et-btn-${size}`, block && "et-btn-block", extra]
    .filter(Boolean)
    .join(" ");
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** primary : un seul par vue · secondary (défaut) · quiet : tertiaire · danger : destructif */
  variant?: Variant;
  /** md = 44 px (tactile, défaut) · sm = 36 px (desktop) · lg = 56 px (tablette atelier) */
  size?: Size;
  block?: boolean;
  loading?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ variant = "secondary", size = "md", block, loading, className, children, disabled, type = "button", ...rest }: ButtonProps) {
  return (
    <button {...rest} type={type} disabled={disabled || loading} aria-busy={loading || undefined} className={classes(variant, size, block, className)}>
      {children}
    </button>
  );
}

export interface ButtonLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
  variant?: Variant;
  size?: Size;
  block?: boolean;
  children: ReactNode;
}

export function ButtonLink({ href, variant = "secondary", size = "md", block, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link href={href} {...rest} className={classes(variant, size, block, className)}>
      {children}
    </Link>
  );
}
