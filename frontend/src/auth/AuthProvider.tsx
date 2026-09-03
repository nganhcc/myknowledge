import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  fetchMe,
  login,
  logout as clearStoredSession,
  register,
} from "../api/auth";
import { ApiError } from "../api/client";
import { getAccessToken } from "../api/token";
import {
  AuthContext,
  type AuthContextValue,
  type AuthStatus,
} from "./AuthContext";
import type { UserCreate, UserResponse } from "../types/api";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<UserResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const restoreSession = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setError(null);
      setStatus("unauthenticated");
      return;
    }

    setStatus("loading");
    setError(null);

    try {
      const currentUser = await fetchMe();
      setUser(currentUser);
      setStatus("authenticated");
    } catch (caught) {
      if (caught instanceof ApiError && caught.kind === "unauthorized") {
        clearStoredSession();
        setUser(null);
        setError(null);
        setStatus("unauthenticated");
        return;
      }

      setUser(null);
      setError(caught instanceof Error ? caught : new Error("Unable to restore your session."));
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  const signIn = useCallback(async (email: string, password: string) => {
    setIsSubmitting(true);
    setError(null);

    try {
      await login(email, password);
      const currentUser = await fetchMe();
      setUser(currentUser);
      setStatus("authenticated");
    } catch (caught) {
      clearStoredSession();
      setUser(null);
      setStatus("unauthenticated");
      const authError = caught instanceof Error ? caught : new Error("Unable to sign in.");
      setError(authError);
      throw authError;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const signUp = useCallback(async (newUser: UserCreate) => {
    setIsSubmitting(true);
    setError(null);

    try {
      return await register(newUser);
    } catch (caught) {
      const authError = caught instanceof Error ? caught : new Error("Unable to create your account.");
      setError(authError);
      throw authError;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const signOut = useCallback(() => {
    clearStoredSession();
    setUser(null);
    setError(null);
    setStatus("unauthenticated");
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      error,
      isSubmitting,
      signIn,
      signUp,
      signOut,
      retrySession: restoreSession,
      clearError,
    }),
    [status, user, error, isSubmitting, signIn, signUp, signOut, restoreSession, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
