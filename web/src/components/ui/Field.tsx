"use client";

import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

interface FieldShellProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: ReactNode;
}

function FieldShell({ id, label, hint, error, required, className, children }: FieldShellProps) {
  const message = error ?? hint;
  return (
    <div className={["et-field", error && "et-field-error", className].filter(Boolean).join(" ")}>
      <label className="et-field-label" htmlFor={id}>
        {label}
        {required ? (
          <span className="et-field-required" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children}
      {message ? (
        <span className="et-field-hint" id={`${id}-hint`} role={error ? "alert" : undefined}>
          {message}
        </span>
      ) : null}
    </div>
  );
}

function a11y(id: string, hint?: string, error?: string) {
  return {
    id,
    "aria-describedby": hint || error ? `${id}-hint` : undefined,
    "aria-invalid": error ? true : undefined,
  } as const;
}

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  /** Message d'erreur : remplace l'aide et marque le champ invalide. */
  error?: string;
  /** Police mono pour VIN, références, kilométrage. */
  mono?: boolean;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, mono, className, id, required, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <FieldShell id={fid} label={label} hint={hint} error={error} required={required} className={className}>
      <input ref={ref} {...rest} {...a11y(fid, hint, error)} required={required} className={`et-input${mono ? " et-input-mono" : ""}`} />
    </FieldShell>
  );
});

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, hint, error, className, id, required, children, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <FieldShell id={fid} label={label} hint={hint} error={error} required={required} className={className}>
      <select ref={ref} {...rest} {...a11y(fid, hint, error)} required={required} className="et-input">
        {children}
      </select>
    </FieldShell>
  );
});

export interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const TextAreaField = forwardRef<HTMLTextAreaElement, TextAreaFieldProps>(function TextAreaField(
  { label, hint, error, className, id, required, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <FieldShell id={fid} label={label} hint={hint} error={error} required={required} className={className}>
      <textarea ref={ref} {...rest} {...a11y(fid, hint, error)} required={required} className="et-input" />
    </FieldShell>
  );
});
