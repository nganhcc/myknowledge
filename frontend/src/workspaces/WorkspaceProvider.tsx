import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createWorkspace as createWorkspaceRequest,
  deleteWorkspace,
  listWorkspaces,
  updateWorkspace,
} from "../api/workspaces";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/useAuth";
import type { WorkspaceResponse } from "../types/api";
import { WorkspaceContext, type WorkspaceContextValue, type WorkspaceStatus } from "./WorkspaceContext";

const workspaceStoragePrefix = "myknowledge_selected_workspace";

interface WorkspaceProviderProps {
  children: ReactNode;
}

function storageKey(userId: string): string {
  return `${workspaceStoragePrefix}:${userId}`;
}

export function WorkspaceProvider({ children }: WorkspaceProviderProps) {
  const { status: authStatus, user, signOut } = useAuth();
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [status, setStatus] = useState<WorkspaceStatus>("loading");
  const [error, setError] = useState<Error | null>(null);

  const selectWorkspace = useCallback(
    (workspaceId: string) => {
      if (!workspaces.some((workspace) => workspace.id === workspaceId)) return;
      setSelectedWorkspaceId(workspaceId);
      if (user) localStorage.setItem(storageKey(user.id), workspaceId);
    },
    [user, workspaces],
  );

  const refreshWorkspaces = useCallback(async () => {
    if (!user) return;

    setStatus("loading");
    setError(null);

    try {
      const nextWorkspaces = await listWorkspaces();
      setWorkspaces(nextWorkspaces);

      const savedWorkspaceId = localStorage.getItem(storageKey(user.id));
      const nextSelectedWorkspace =
        nextWorkspaces.find((workspace) => workspace.id === savedWorkspaceId) ??
        nextWorkspaces[0] ??
        null;

      setSelectedWorkspaceId(nextSelectedWorkspace?.id ?? null);
      if (nextSelectedWorkspace) {
        localStorage.setItem(storageKey(user.id), nextSelectedWorkspace.id);
      } else {
        localStorage.removeItem(storageKey(user.id));
      }
      setStatus("ready");
    } catch (caught) {
      if (caught instanceof ApiError && caught.kind === "unauthorized") {
        signOut();
        return;
      }
      setError(caught instanceof Error ? caught : new Error("Unable to load workspaces."));
      setStatus("error");
    }
  }, [signOut, user]);

  useEffect(() => {
    if (authStatus !== "authenticated" || !user) return;
    void refreshWorkspaces();
  }, [authStatus, refreshWorkspaces, user]);

  const createWorkspace = useCallback(async (name: string) => {
    const workspace = await createWorkspaceRequest({ name });
    setWorkspaces((current) => [...current, workspace]);
    setSelectedWorkspaceId(workspace.id);
    if (user) localStorage.setItem(storageKey(user.id), workspace.id);
    return workspace;
  }, [user]);

  const renameWorkspace = useCallback(async (workspaceId: string, name: string) => {
    const workspace = await updateWorkspace(workspaceId, { name });
    setWorkspaces((current) =>
      current.map((item) => (item.id === workspace.id ? workspace : item)),
    );
    return workspace;
  }, []);

  const removeWorkspace = useCallback(async (workspaceId: string) => {
    await deleteWorkspace(workspaceId);
    const nextWorkspaces = workspaces.filter((workspace) => workspace.id !== workspaceId);
    setWorkspaces(nextWorkspaces);

    if (selectedWorkspaceId === workspaceId) {
      const nextSelectedWorkspace = nextWorkspaces[0] ?? null;
      setSelectedWorkspaceId(nextSelectedWorkspace?.id ?? null);
      if (user) {
        if (nextSelectedWorkspace) {
          localStorage.setItem(storageKey(user.id), nextSelectedWorkspace.id);
        } else {
          localStorage.removeItem(storageKey(user.id));
        }
      }
    }
  }, [selectedWorkspaceId, user, workspaces]);

  const selectedWorkspace =
    workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null;

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      workspaces,
      selectedWorkspace,
      selectedWorkspaceId,
      status,
      error,
      selectWorkspace,
      refreshWorkspaces,
      createWorkspace,
      renameWorkspace,
      removeWorkspace,
    }),
    [
      workspaces,
      selectedWorkspace,
      selectedWorkspaceId,
      status,
      error,
      selectWorkspace,
      refreshWorkspaces,
      createWorkspace,
      renameWorkspace,
      removeWorkspace,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
