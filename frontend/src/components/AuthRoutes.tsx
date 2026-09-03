import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { PageLoading } from "./AuthLayout";

export function RequireAuth() {
  const { status, error, retrySession } = useAuth();
  const location = useLocation();

  if (status === "loading") return <PageLoading label="Restoring your session…" />;
  if (status === "error") {
    return (
      <main className="centered-page">
        <div className="session-error" role="alert">
          <h1>We couldn’t restore your session</h1>
          <p>{error?.message ?? "Please try again."}</p>
          <button className="primary-button" type="button" onClick={() => void retrySession()}>
            Try again
          </button>
        </div>
      </main>
    );
  }
  if (status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}

export function PublicOnly() {
  const { status } = useAuth();
  if (status === "loading") return <PageLoading label="Restoring your session…" />;
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <Outlet />;
}
