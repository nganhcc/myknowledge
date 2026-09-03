import type { ReactNode } from "react";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-brand">AI Knowledge Base</div>
        <h1 id="auth-title">{title}</h1>
        <p className="auth-subtitle">{subtitle}</p>
        {children}
        <div className="auth-footer">{footer}</div>
      </section>
    </main>
  );
}

interface FormFieldProps {
  id: string;
  label: string;
  error?: string;
  children: ReactNode;
}

export function FormField({ id, label, error, children }: FormFieldProps) {
  const errorId = `${id}-error`;
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error ? (
        <p className="field-error" id={errorId}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function AuthError({ message }: { message: string }) {
  return (
    <div className="form-error" role="alert">
      {message}
    </div>
  );
}

export function PageLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <main className="centered-page">
      <p>{label}</p>
    </main>
  );
}
