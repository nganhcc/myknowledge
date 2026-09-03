import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import type { WorkspaceResponse } from "../types/api";
import { useWorkspace } from "../workspaces/useWorkspace";

function actionError(caught: unknown, fallback: string): string {
  if (caught instanceof ApiError) return caught.message;
  return caught instanceof Error ? caught.message : fallback;
}

function canRename(workspace: WorkspaceResponse): boolean {
  return workspace.role === "OWNER" || workspace.role === "ADMIN";
}

function canDelete(workspace: WorkspaceResponse): boolean {
  return workspace.role === "OWNER";
}

export function WorkspacePage() {
  const {
    workspaces,
    selectedWorkspaceId,
    status,
    error,
    refreshWorkspaces,
    selectWorkspace,
    createWorkspace,
    renameWorkspace,
    removeWorkspace,
  } = useWorkspace();
  const [isCreating, setIsCreating] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState("");
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  if (status === "error") {
    return (
      <section className="state-card" role="alert">
        <span className="state-icon">!</span>
        <h2>We couldn’t load your workspaces</h2>
        <p>{error?.message ?? "Please try again."}</p>
        <button className="primary-button" type="button" onClick={() => void refreshWorkspaces()}>
          Try again
        </button>
      </section>
    );
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = newWorkspaceName.trim();
    if (!name) return;

    setIsSaving(true);
    setActionErrorMessage(null);
    try {
      await createWorkspace(name);
      setNewWorkspaceName("");
      setIsCreating(false);
    } catch (caught) {
      setActionErrorMessage(actionError(caught, "Unable to create the workspace."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRename(event: FormEvent<HTMLFormElement>, workspaceId: string) {
    event.preventDefault();
    const name = editingName.trim();
    if (!name) return;

    setIsSaving(true);
    setActionErrorMessage(null);
    try {
      await renameWorkspace(workspaceId, name);
      setEditingWorkspaceId(null);
    } catch (caught) {
      setActionErrorMessage(actionError(caught, "Unable to rename the workspace."));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(workspace: WorkspaceResponse) {
    if (!window.confirm(`Delete “${workspace.name}”? This cannot be undone.`)) return;

    setIsSaving(true);
    setActionErrorMessage(null);
    try {
      await removeWorkspace(workspace.id);
    } catch (caught) {
      setActionErrorMessage(actionError(caught, "Unable to delete the workspace."));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="workspace-page" aria-labelledby="workspace-page-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Workspace management</p>
          <h2 id="workspace-page-title">Your workspaces</h2>
          <p className="page-description">Create a focused space for every team, project, or knowledge base.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => setIsCreating((current) => !current)}>
          {isCreating ? "Cancel" : "New workspace"}
        </button>
      </div>

      {isCreating ? (
        <form className="create-workspace-card" onSubmit={(event) => void handleCreate(event)}>
          <div>
            <h3>Create a workspace</h3>
            <p>Give your new knowledge base a clear name.</p>
          </div>
          <div className="inline-form">
            <label className="sr-only" htmlFor="new-workspace-name">Workspace name</label>
            <input
              id="new-workspace-name"
              value={newWorkspaceName}
              onChange={(event) => setNewWorkspaceName(event.target.value)}
              placeholder="e.g. Product team"
              autoFocus
              required
              maxLength={120}
            />
            <button className="primary-button" type="submit" disabled={isSaving || !newWorkspaceName.trim()}>
              Create
            </button>
          </div>
        </form>
      ) : null}

      {actionErrorMessage ? (
        <div className="form-error" role="alert">{actionErrorMessage}</div>
      ) : null}

      {workspaces.length === 0 ? (
        <div className="state-card empty-state">
          <span className="state-icon">✦</span>
          <h2>Start your first workspace</h2>
          <p>Workspaces keep your documents, conversations, and collaborators organized.</p>
          <button className="primary-button" type="button" onClick={() => setIsCreating(true)}>
            Create workspace
          </button>
        </div>
      ) : (
        <div className="workspace-grid">
          {workspaces.map((workspace) => {
            const isSelected = workspace.id === selectedWorkspaceId;
            const isEditing = workspace.id === editingWorkspaceId;

            return (
              <article className={`workspace-card${isSelected ? " selected" : ""}`} key={workspace.id}>
                <div className="workspace-card-topline">
                  <span className="workspace-symbol" aria-hidden="true">{workspace.name.slice(0, 1).toUpperCase()}</span>
                  <span className={`role-badge role-${workspace.role.toLowerCase()}`}>{workspace.role}</span>
                </div>

                {isEditing ? (
                  <form onSubmit={(event) => void handleRename(event, workspace.id)}>
                    <label className="sr-only" htmlFor={`workspace-name-${workspace.id}`}>Workspace name</label>
                    <input
                      id={`workspace-name-${workspace.id}`}
                      className="workspace-name-input"
                      value={editingName}
                      onChange={(event) => setEditingName(event.target.value)}
                      autoFocus
                      required
                      maxLength={120}
                    />
                    <div className="card-actions">
                      <button className="primary-button compact-button" type="submit" disabled={isSaving || !editingName.trim()}>Save</button>
                      <button className="text-button" type="button" onClick={() => setEditingWorkspaceId(null)}>Cancel</button>
                    </div>
                  </form>
                ) : (
                  <>
                    <h3>{workspace.name}</h3>
                    <p className="workspace-meta">Created {new Date(workspace.created_at).toLocaleDateString()}</p>
                    <div className="card-actions">
                      <button
                        className={isSelected ? "selected-button" : "secondary-button compact-button"}
                        type="button"
                        onClick={() => selectWorkspace(workspace.id)}
                        disabled={isSelected}
                      >
                        {isSelected ? "Selected" : "Use workspace"}
                      </button>
                      {canRename(workspace) ? (
                        <button
                          className="text-button"
                          type="button"
                          onClick={() => {
                            setEditingWorkspaceId(workspace.id);
                            setEditingName(workspace.name);
                          }}
                        >
                          Rename
                        </button>
                      ) : null}
                      {canDelete(workspace) ? (
                        <button className="danger-button" type="button" onClick={() => void handleDelete(workspace)} disabled={isSaving}>
                          Delete
                        </button>
                      ) : null}
                    </div>
                  </>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
