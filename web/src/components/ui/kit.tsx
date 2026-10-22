import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./ui.css";

type ButtonKind = "primary" | "secondary" | "ghost" | "danger" | "plain";

export function Button({
  kind = "plain",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind }) {
  const kindClass = kind === "plain" ? "" : ` btn-${kind}`;
  return <button type={type} className={`btn${kindClass} ${className}`.trim()} {...props} />;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      {label}
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return (
    <p className="error-text" role="alert">
      {children}
    </p>
  );
}

export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article" | "form";
}) {
  return <Tag className={`clay card ${className}`.trim()}>{children}</Tag>;
}

export function PageHeader({
  title,
  eyebrow,
  actions,
}: {
  title: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
      </div>
      {actions}
    </header>
  );
}

export function Switch({
  checked,
  label,
  onChange,
  disabled,
}: {
  checked: boolean;
  label: string;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      className="switch"
      disabled={disabled}
      onClick={() => onChange(!checked)}
    />
  );
}
