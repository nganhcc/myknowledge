import { http } from "./client";
import type { DocumentResponse, DocumentStatusResponse } from "../types/api";

export function listDocuments(workspaceId: string): Promise<DocumentResponse[]> {
  return http.get<DocumentResponse[]>(
    `/api/v1/workspaces/${workspaceId}/documents`,
  );
}

export function getDocument(
  workspaceId: string,
  documentId: string,
): Promise<DocumentResponse> {
  return http.get<DocumentResponse>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}`,
  );
}

export function uploadDocument(
  workspaceId: string,
  file: File,
): Promise<DocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  return http.postForm<DocumentResponse>(
    `/api/v1/workspaces/${workspaceId}/documents`,
    form,
  );
}

export function getDocumentStatus(
  workspaceId: string,
  documentId: string,
): Promise<DocumentStatusResponse> {
  return http.get<DocumentStatusResponse>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}/status`,
  );
}

export function deleteDocument(
  workspaceId: string,
  documentId: string,
): Promise<void> {
  return http.delete<void>(
    `/api/v1/workspaces/${workspaceId}/documents/${documentId}`,
  );
}