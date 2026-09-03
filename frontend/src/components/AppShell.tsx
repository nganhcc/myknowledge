import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { useWorkspace } from "../workspaces/useWorkspace";
import { PageLoading } from "./AuthLayout";

export function AppShell() {
  const { user, signOut } = useAuth();
  const {
    workspaces,
    selectedWorkspace,
    selectedWorkspaceId,
    selectWorkspace,
    status: workspaceStatus,
  } = useWorkspace();
  const location = useLocation();
  const isDocumentsPage = location.pathname.startsWith("/documents");
  const isChatPage = location.pathname.startsWith("/chat");

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark" aria-hidden="true">K</span>
          <span>Knowledge Base</span>
        </div>

        <div className="workspace-switcher">
          <label htmlFor="workspace-switcher">Workspace</label>
          {workspaceStatus === "loading" ? (
            <p className="sidebar-muted">Loading workspaces…</p>
          ) : (
            <select
              id="workspace-switcher"
              value={selectedWorkspaceId ?? ""}
              onChange={(event) => selectWorkspace(event.target.value)}
              disabled={workspaces.length === 0}
            >
              {workspaces.length === 0 ? (
                <option value="">No workspaces</option>
              ) : (
                workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))
              )}
            </select>
          )}
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <NavLink
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            to="/workspaces"
          >
            <span aria-hidden="true">▦</span>
            Workspaces
          </NavLink>
          <NavLink
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            to="/documents"
          >
            <span aria-hidden="true">▤</span>
            Documents
          </NavLink>
          <NavLink
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            to="/chat"
          >
            <span aria-hidden="true">✦</span>
            Chat
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="avatar" aria-hidden="true">{user?.name.slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{user?.name}</strong>
              <span>{user?.email}</span>
            </div>
          </div>
          <button className="sidebar-logout" type="button" onClick={signOut}>
            Log out
          </button>
        </div>
      </aside>

      <div className="app-content">
        <header className="app-header">
          <div>
            <p className="header-kicker">{selectedWorkspace?.name ?? "Your workspace"}</p>
            <h1>{isDocumentsPage ? "Documents" : isChatPage ? "Chat" : "Workspace overview"}</h1>
          </div>
          <div className="header-user">
            <span className="avatar avatar-small" aria-hidden="true">{user?.name.slice(0, 1).toUpperCase()}</span>
            <span>{user?.name}</span>
          </div>
        </header>
        <main className="app-main">
          {workspaceStatus === "loading" ? <PageLoading label="Loading your workspaces…" /> : <Outlet />}
        </main>
      </div>
    </div>
  );
}
