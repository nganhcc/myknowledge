export type AuthField = "email" | "password" | "name" | "confirmPassword";
export type FieldErrors = Partial<Record<AuthField, string>>;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email: string): string | undefined {
  if (!email.trim()) return "Email is required.";
  if (email.length > 255 || !emailPattern.test(email)) {
    return "Enter a valid email address.";
  }
  return undefined;
}

export function validatePassword(password: string): string | undefined {
  if (!password) return "Password is required.";
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (password.length > 128) return "Password must be 128 characters or fewer.";
  return undefined;
}

export function validateLogin(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  const emailError = validateEmail(email);
  const passwordError = validatePassword(password);
  if (emailError) errors.email = emailError;
  if (passwordError) errors.password = passwordError;
  return errors;
}

export function validateRegistration(
  name: string,
  email: string,
  password: string,
  confirmPassword: string,
): FieldErrors {
  const errors = validateLogin(email, password);
  const trimmedName = name.trim();
  if (!trimmedName) errors.name = "Name is required.";
  else if (trimmedName.length > 100) errors.name = "Name must be 100 characters or fewer.";
  if (!confirmPassword) errors.confirmPassword = "Please confirm your password.";
  else if (password !== confirmPassword) errors.confirmPassword = "Passwords do not match.";
  return errors;
}
