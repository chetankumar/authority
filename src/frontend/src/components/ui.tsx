import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white hover:opacity-90 disabled:opacity-40",
  secondary: "border border-line bg-surface text-ink hover:bg-accent-wash disabled:opacity-40",
  ghost: "text-ink-soft hover:bg-accent-wash disabled:opacity-40",
  danger: "bg-danger text-white hover:opacity-90 disabled:opacity-40",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({ variant = "secondary", className = "", ...rest }: ButtonProps) {
  return (
    <button
      className={`h-8 rounded-control px-3 text-[0.875rem] transition-opacity ${BUTTON_STYLES[variant]} ${className}`}
      {...rest}
    />
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[0.75rem] tracking-[0.02em] text-ink-soft">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-[0.75rem] text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-[0.75rem] text-ink-faint">{hint}</span>
      ) : null}
    </label>
  );
}

const CONTROL = "h-8 w-full rounded-control border border-line bg-surface px-2 text-[0.875rem] text-ink outline-none focus:border-accent";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}
