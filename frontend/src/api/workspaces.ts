import { http } from "./client";
import type {
  MemberAdd,
  MemberResponse,
  MemberRoleUpdate,
  WorkspaceCreate,
  WorkspaceResponse,
  WorkspaceUpdate,
} from "../types/api";

export function listWorkspaces(): Promise<WorkspaceResponse[]> {
  return http.get<WorkspaceResponse[]>("/api/v1/workspaces");
}

export function createWorkspace(
  payload: WorkspaceCreate,
): Promise<WorkspaceResponse> {
  return http.post<WorkspaceResponse>("/api/v1/workspaces", payload);
}

export function getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
  return http.get<WorkspaceResponse>(`/api/v1/workspaces/${workspaceId}`);
}

export function updateWorkspace(
  workspaceId: string,
  payload: WorkspaceUpdate,
): Promise<WorkspaceResponse> {
  return http.patch<WorkspaceResponse>(
    `/api/v1/workspaces/${workspaceId}`,
    payload,
  );
}

export function deleteWorkspace(workspaceId: string): Promise<void> {
  return http.delete<void>(`/api/v1/workspaces/${workspaceId}`);
}

// --- Membership ---

export function listMembers(workspaceId: string): Promise<MemberResponse[]> {
  return http.get<MemberResponse[]>(
    `/api/v1/workspaces/${workspaceId}/members`,
  );
}

export function addMember(
  workspaceId: string,
  payload: MemberAdd,
): Promise<MemberResponse> {
  return http.post<MemberResponse>(
    `/api/v1/workspaces/${workspaceId}/members`,
    payload,
  );
}

export function updateMemberRole(
  workspaceId: string,
  userId: string,
  payload: MemberRoleUpdate,
): Promise<MemberResponse> {
  return http.patch<MemberResponse>(
    `/api/v1/workspaces/${workspaceId}/members/${userId}`,
    payload,
  );
}

export function removeMember(
  workspaceId: string,
  userId: string,
): Promise<void> {
  return http.delete<void>(
    `/api/v1/workspaces/${workspaceId}/members/${userId}`,
  );
}