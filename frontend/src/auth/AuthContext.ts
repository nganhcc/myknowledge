import { createContext } from "react";
import type { UserCreate, UserResponse } from "../types/api";

export type AuthStatus =
  | "loading"
  | "authenticated"
  | "unauthenticated"
  | "error";

export interface AuthContextValue {
  status: AuthStatus;
  user: UserResponse | null;
  error: Error | null;
  isSubmitting: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (user: UserCreate) => Promise<UserResponse>;
  signOut: () => void;
  retrySession: () => Promise<void>;
  clearError: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
