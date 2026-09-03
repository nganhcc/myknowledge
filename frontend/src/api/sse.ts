import { API_BASE_URL, responseKind, messageFor } from "./client";
import { getAccessToken } from "./token";
import type { ChatRequest } from "../types/api";

/**
 * SSE chat streaming.
 *
 * `POST /api/v1/chat` requires a JSON body and an Authorization header, so
 * native `EventSource` cannot be used. We read the stream with `fetch()` and
 * parse the Server-Sent Events manually.
 *
 * Event protocol (confirmed against the backend service):
 *   event: token -> data: {"token": "text chunk"}
 *   event: error -> data: {"detail": "message"}
 *   event: done  -> data: {"message_id": "...", "total_tokens": N}
 */

export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onDone: (messageId: string, totalTokens: number) => void;
  onError: (detail: string) => void;
  /** Called when the stream ends without an explicit `done` event. */
  onUnexpectedEnd?: () => void;
}

interface SseFrame {
  event: string | null;
  data: string;
}

/** Dispatch a single SSE frame (complete event + data payload). */
function dispatchFrame(frame: SseFrame, callbacks: ChatStreamCallbacks): boolean {
  const { event, data } = frame;
  if (!data) return false;

  if (event === "token") {
    try {
      const payload = JSON.parse(data) as { token?: string };
      if (typeof payload.token === "string") {
        callbacks.onToken(payload.token);
      }
    } catch {
      callbacks.onError("Received an invalid token chunk.");
    }
    return false;
  }

  if (event === "done") {
    try {
      const payload = JSON.parse(data) as {
        message_id?: string;
        total_tokens?: number;
      };
      callbacks.onDone(payload.message_id ?? "", payload.total_tokens ?? 0);
      return true;
    } catch {
      callbacks.onError("Received an invalid completion event.");
      return true;
    }
  }

  if (event === "error") {
    let detail = data;
    try {
      const payload = JSON.parse(data) as { detail?: string };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // keep the raw payload as the detail
    }
    callbacks.onError(detail);
  }
  return false;
}

export async function streamChat(
  request: ChatRequest,
  callbacks: ChatStreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    callbacks.onError("Cannot reach the server. Is the backend running?");
    return;
  }

  // Non-2xx responses carry a JSON error body, not an SSE stream.
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = null;
    }
    const kind = responseKind(response.status);
    callbacks.onError(messageFor(kind, detail));
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError("The server returned an empty stream.");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let eventName: string | null = null;
  let dataLines: string[] = [];
  let finished = false;

  try {
    while (!finished) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are delimited by blank lines (\n\n).
      let sepIndex: number;
      while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawFrame = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);

        for (const rawLine of rawFrame.split("\n")) {
          const line = rawLine.replace(/\r$/, "");
          if (line.startsWith("event:")) {
            eventName = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }

        if (eventName === null && dataLines.length === 0) continue;
        const shouldStop = dispatchFrame(
          { event: eventName, data: dataLines.join("\n") },
          callbacks,
        );
        eventName = null;
        dataLines = [];
        if (shouldStop) finished = true;
      }
    }

    // A trailing frame without a terminating blank line.
    if (!finished && (eventName !== null || dataLines.length > 0)) {
      dispatchFrame(
        { event: eventName, data: dataLines.join("\n") },
        callbacks,
      );
    }

    if (!finished) callbacks.onUnexpectedEnd?.();
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "AbortError")) {
      callbacks.onUnexpectedEnd?.();
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // reader already released/cancelled
    }
  }
}
