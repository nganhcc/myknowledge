import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AuthError, AuthLayout, FormField } from "../components/AuthLayout";
import { useAuth } from "../auth/useAuth";
import { validateRegistration, type FieldErrors } from "../auth/validation";

export function RegisterPage() {
  const { signUp, isSubmitting, error, clearError } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validateRegistration(name, email, password, confirmPassword);
    setFieldErrors(errors);
    clearError();
    if (Object.keys(errors).length > 0) return;

    try {
      await signUp({ name: name.trim(), email: email.trim(), password });
      navigate("/login", {
        replace: true,
        state: { message: "Your account was created. You can now sign in." },
      });
    } catch {
      // The provider stores the API error for display in this form.
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start organizing your team’s knowledge."
      footer={
        <>
          Already have an account? <Link to="/login">Sign in</Link>
        </>
      }
    >
      {error ? <AuthError message={error.message} /> : null}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <FormField id="name" label="Name" error={fieldErrors.name}>
          <input
            id="name"
            type="text"
            autoComplete="name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              clearError();
            }}
            aria-invalid={Boolean(fieldErrors.name)}
            aria-describedby={fieldErrors.name ? "name-error" : undefined}
            required
          />
        </FormField>
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
            autoComplete="new-password"
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
        <FormField id="confirm-password" label="Confirm password" error={fieldErrors.confirmPassword}>
          <input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => {
              setConfirmPassword(event.target.value);
              clearError();
            }}
            aria-invalid={Boolean(fieldErrors.confirmPassword)}
            aria-describedby={fieldErrors.confirmPassword ? "confirm-password-error" : undefined}
            required
          />
        </FormField>
        <button className="primary-button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthLayout>
  );
}
