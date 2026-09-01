export type WorkspaceRole = "OWNER" | "ADMIN" | "MEMBER";

export type DocumentStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

export type MessageRole = "USER" | "ASSISTANT" | "SYSTEM";

// --- Auth ---

export interface UserCreate {
  email: string;
  password: string;
  name: string;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type?: string;
}

// --- Workspaces ---

export interface WorkspaceCreate {
  name: string;
}

export interface WorkspaceUpdate {
  name: string;
}

export interface WorkspaceResponse {
  id: string;
  name: string;
  created_by: string;
  created_at: string;
  /** Role of the calling user within this workspace. */
  role: WorkspaceRole;
}

// --- Members ---

export interface MemberAdd {
  email: string;
  role?: WorkspaceRole;
}

export interface MemberRoleUpdate {
  role: WorkspaceRole;
}

export interface MemberResponse {
  user_id: string;
  email: string;
  name: string;
  role: WorkspaceRole;
}

// --- Documents ---

export interface DocumentResponse {
  id: string;
  workspace_id: string;
  title: string;
  filename: string;
  mime_type: string;
  size: number;
  status: DocumentStatus;
  created_at: string;
}

export interface DocumentStatusResponse {
  id: string;
  status: DocumentStatus;
  retry_count: number;
}

// --- Chat ---

export interface ChatRequest {
  workspace_id: string;
  conversation_id?: string | null;
  message: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page: number | null;
}

export interface ConversationResponse {
  id: string;
  workspace_id: string;
  title: string;
  created_at: string;
}

export interface MessageResponse {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[] | null;
  token_count: number | null;
  created_at: string;
}

// --- Errors ---

export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HttpValidationError {
  detail: ValidationErrorItem[];
}

/** Generic `{"detail": ...}` body returned by non-422 error handlers. */
export interface ErrorDetail {
  detail: string | ValidationErrorItem[];
}