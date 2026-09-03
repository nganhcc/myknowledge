import { createContext } from "react";
import type { WorkspaceResponse } from "../types/api";

export type WorkspaceStatus = "loading" | "ready" | "error";

export interface WorkspaceContextValue {
  workspaces: WorkspaceResponse[];
  selectedWorkspace: WorkspaceResponse | null;
  selectedWorkspaceId: string | null;
  status: WorkspaceStatus;
  error: Error | null;
  selectWorkspace: (workspaceId: string) => void;
  refreshWorkspaces: () => Promise<void>;
  createWorkspace: (name: string) => Promise<WorkspaceResponse>;
  renameWorkspace: (workspaceId: string, name: string) => Promise<WorkspaceResponse>;
  removeWorkspace: (workspaceId: string) => Promise<void>;
}

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
