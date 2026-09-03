import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { AuthError, AuthLayout, FormField } from "../components/AuthLayout";
import { useAuth } from "../auth/useAuth";
import { validateLogin, type FieldErrors } from "../auth/validation";

interface LoginLocationState {
  from?: { pathname?: string; search?: string; hash?: string };
  message?: string;
}

function getReturnPath(state: unknown): string {
  if (!state || typeof state !== "object" || !("from" in state)) return "/";
  const from = (state as LoginLocationState).from;
  if (!from?.pathname) return "/";
  return `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`;
}

export function LoginPage() {
  const { signIn, isSubmitting, error, clearError } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const locationState = location.state as LoginLocationState | null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validateLogin(email, password);
    setFieldErrors(errors);
    clearError();
    if (Object.keys(errors).length > 0) return;

    try {
      await signIn(email, password);
      navigate(getReturnPath(location.state), { replace: true });
    } catch {
      // The provider stores the API error for display in this form.
    }
  }

  const errorMessage =
    error instanceof ApiError && error.kind === "unauthorized"
      ? "Invalid email or password."
      : error?.message;

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your knowledge base."
      footer={
        <>
          Don’t have an account? <Link to="/register">Create one</Link>
        </>
      }
    >
      {locationState?.message ? <div className="form-success">{locationState.message}</div> : null}
      {errorMessage ? <AuthError message={errorMessage} /> : null}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <FormField id="email" label="Email" error={fieldErrors.email}>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              clearError();
            }}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? "email-error" : undefined}
            required
          />
        </FormField>
        <FormField id="password" label="Password" error={fieldErrors.password}>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              clearError();
            }}
            aria-invalid={Boolean(fieldErrors.password)}
            aria-describedby={fieldErrors.password ? "password-error" : undefined}
            required
          />
        </FormField>
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthLayout>
  );
}
