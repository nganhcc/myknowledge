import { http } from "./client";
import type {
  ConversationResponse,
  MessageResponse,
} from "../types/api";

export function listConversations(
  workspaceId: string,
): Promise<ConversationResponse[]> {
  return http.get<ConversationResponse[]>(
    `/api/v1/workspaces/${workspaceId}/conversations`,
  );
}

export function getConversation(
  conversationId: string,
): Promise<ConversationResponse> {
  return http.get<ConversationResponse>(
    `/api/v1/conversations/${conversationId}`,
  );
}

export function listMessages(
  conversationId: string,
): Promise<MessageResponse[]> {
  return http.get<MessageResponse[]>(
    `/api/v1/conversations/${conversationId}/messages`,
  );
}