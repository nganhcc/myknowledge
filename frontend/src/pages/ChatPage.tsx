import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { listConversations, listMessages } from "../api/chat";
import { streamChat } from "../api/sse";
import { useAuth } from "../auth/useAuth";
import type { ConversationResponse, MessageResponse } from "../types/api";
import { useWorkspace } from "../workspaces/useWorkspace";

type LoadStatus = "loading" | "ready" | "error";

interface FailedTurn {
  prompt: string;
  userMessageId: string;
  assistantMessageId: string;
}

function errorMessage(caught: unknown, fallback: string): string {
  if (caught instanceof ApiError) return caught.message;
  return caught instanceof Error ? caught.message : fallback;
}

function makeLocalId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatConversationDate(date: string): string {
  return new Date(date).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatCitationPage(page: number | null): string {
  return page === null ? "Page unavailable" : `Page ${page}`;
}

export function ChatPage() {
  const { selectedWorkspace, selectedWorkspaceId } = useWorkspace();
  const { signOut } = useAuth();
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [conversationStatus, setConversationStatus] = useState<LoadStatus>("ready");
  const [messagesStatus, setMessagesStatus] = useState<LoadStatus>("ready");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [failedTurn, setFailedTurn] = useState<FailedTurn | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);

  const handleUnauthorized = useCallback(
    (caught: unknown) => {
      if (caught instanceof ApiError && caught.kind === "unauthorized") {
        signOut();
        return true;
      }
      return false;
    },
    [signOut],
  );

  const loadConversationMessages = useCallback(
    async (conversationId: string) => {
      setMessagesStatus("loading");
      setLoadError(null);
      try {
        const nextMessages = await listMessages(conversationId);
        setMessages(nextMessages);
        setMessagesStatus("ready");
      } catch (caught) {
        if (handleUnauthorized(caught)) return;
        setMessagesStatus("error");
        setLoadError(errorMessage(caught, "Unable to load this conversation."));
      }
    },
    [handleUnauthorized],
  );

  useEffect(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsStreaming(false);
    setStreamError(null);
    setFailedTurn(null);

    if (!selectedWorkspaceId) {
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      setConversationStatus("ready");
      setMessagesStatus("ready");
      setLoadError(null);
      return;
    }

    let cancelled = false;
    setConversationStatus("loading");
    setMessagesStatus("ready");
    setLoadError(null);

    void listConversations(selectedWorkspaceId)
      .then((nextConversations) => {
        if (cancelled) return;
        setConversations(nextConversations);
        setActiveConversationId(nextConversations[0]?.id ?? null);
        setConversationStatus("ready");
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        if (handleUnauthorized(caught)) return;
        setConversationStatus("error");
        setLoadError(errorMessage(caught, "Unable to load your conversations."));
      });

    return () => {
      cancelled = true;
    };
  }, [handleUnauthorized, selectedWorkspaceId]);

  useEffect(() => {
    if (!activeConversationId) {
      setMessages([]);
      setMessagesStatus("ready");
      return;
    }
    void loadConversationMessages(activeConversationId);
  }, [activeConversationId, loadConversationMessages]);

  useEffect(() => () => abortControllerRef.current?.abort(), []);

  useEffect(() => {
    const messageList = messageListRef.current;
    if (messageList) messageList.scrollTop = messageList.scrollHeight;
  }, [messages]);

  const refreshAfterStream = useCallback(
    async (workspaceId: string, requestedConversationId: string | null, messageId: string) => {
      const nextConversations = await listConversations(workspaceId);
      setConversations(nextConversations);

      if (requestedConversationId) {
        setActiveConversationId(requestedConversationId);
        const nextMessages = await listMessages(requestedConversationId);
        setMessages(nextMessages);
        setMessagesStatus("ready");
        return;
      }

      // The SSE done event returns the message id, but not the new conversation id.
      // Match that id against refreshed histories to select the new thread.
      const messageResults = await Promise.all(
        nextConversations.map(async (conversation) => ({
          conversation,
          messages: await listMessages(conversation.id),
        })),
      );
      const match = messageResults.find(({ messages: candidateMessages }) =>
        candidateMessages.some((candidate) => candidate.id === messageId),
      );
      const selected = match ?? messageResults[0];
      if (!selected) {
        setActiveConversationId(null);
        setMessages([]);
        return;
      }

      setActiveConversationId(selected.conversation.id);
      setMessages(selected.messages);
      setMessagesStatus("ready");
    },
    [],
  );

  const sendMessage = useCallback(
    async (rawMessage: string) => {
      const message = rawMessage.trim();
      if (!message || !selectedWorkspaceId || isStreaming) return;

      const requestedConversationId = activeConversationId;
      const userMessageId = makeLocalId("user");
      const assistantMessageId = makeLocalId("assistant");
      const now = new Date().toISOString();
      const optimisticUserMessage: MessageResponse = {
        id: userMessageId,
        role: "USER",
        content: message,
        citations: null,
        token_count: null,
        created_at: now,
      };
      const streamingAssistantMessage: MessageResponse = {
        id: assistantMessageId,
        role: "ASSISTANT",
        content: "",
        citations: null,
        token_count: null,
        created_at: now,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        optimisticUserMessage,
        streamingAssistantMessage,
      ]);
      setInput("");
      setStreamError(null);
      setFailedTurn(null);
      setIsStreaming(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;
      let completedMessageId = "";
      let streamCompleted = false;
      let receivedError = false;

      try {
        await streamChat(
          {
            workspace_id: selectedWorkspaceId,
            conversation_id: requestedConversationId,
            message,
          },
          {
            onToken: (token) => {
              setMessages((currentMessages) =>
                currentMessages.map((currentMessage) =>
                  currentMessage.id === assistantMessageId
                    ? { ...currentMessage, content: currentMessage.content + token }
                    : currentMessage,
                ),
              );
            },
            onDone: (messageId) => {
              streamCompleted = true;
              completedMessageId = messageId;
            },
            onError: (detail) => {
              receivedError = true;
              setStreamError(detail);
              setFailedTurn({ prompt: message, userMessageId, assistantMessageId });
            },
            onUnexpectedEnd: () => {
              receivedError = true;
              const detail = "The connection ended before the answer was complete.";
              setStreamError(detail);
              setFailedTurn({ prompt: message, userMessageId, assistantMessageId });
            },
          },
          controller.signal,
        );

        if (streamCompleted && !receivedError && !controller.signal.aborted) {
          try {
            await refreshAfterStream(
              selectedWorkspaceId,
              requestedConversationId,
              completedMessageId,
            );
          } catch (caught) {
            if (handleUnauthorized(caught)) return;
            setStreamError(errorMessage(caught, "The answer arrived, but history could not be refreshed."));
          }
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          if (handleUnauthorized(caught)) return;
          setStreamError(errorMessage(caught, "Unable to send your message."));
          setFailedTurn({ prompt: message, userMessageId, assistantMessageId });
        }
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        setIsStreaming(false);
      }
    },
    [
      activeConversationId,
      handleUnauthorized,
      isStreaming,
      refreshAfterStream,
      selectedWorkspaceId,
    ],
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  }

  function handleNewConversation() {
    if (isStreaming) return;
    setActiveConversationId(null);
    setMessages([]);
    setMessagesStatus("ready");
    setStreamError(null);
    setFailedTurn(null);
  }

  function handleRetry() {
    if (!failedTurn || isStreaming) return;
    setMessages((currentMessages) =>
      currentMessages.filter(
        (message) =>
          message.id !== failedTurn.userMessageId &&
          message.id !== failedTurn.assistantMessageId,
      ),
    );
    setStreamError(null);
    const prompt = failedTurn.prompt;
    setFailedTurn(null);
    void sendMessage(prompt);
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
    setStreamError(null);
    setFailedTurn(null);
  }

  if (!selectedWorkspaceId || !selectedWorkspace) {
    return (
      <section className="state-card" aria-labelledby="chat-empty-workspace-title">
        <span className="state-icon" aria-hidden="true">✦</span>
        <h2 id="chat-empty-workspace-title">Create a workspace first</h2>
        <p>Chat uses your workspace documents to answer questions.</p>
        <Link className="primary-button" to="/workspaces">Go to workspaces</Link>
      </section>
    );
  }

  const activeConversation = conversations.find(
    (conversation) => conversation.id === activeConversationId,
  );

  return (
    <section className="chat-page" aria-labelledby="chat-page-title">
      <div className="page-heading chat-page-heading">
        <div>
          <p className="eyebrow">{selectedWorkspace.name}</p>
          <h2 id="chat-page-title">Ask your knowledge base</h2>
          <p className="page-description">Ask questions and get answers grounded in your workspace documents.</p>
        </div>
        <button className="primary-button" type="button" onClick={handleNewConversation} disabled={isStreaming}>
          New conversation
        </button>
      </div>

      <div className="chat-layout">
        <aside className="conversation-panel" aria-label="Conversations">
          <div className="conversation-panel-header">
            <div>
              <h3>Conversations</h3>
              <p>{conversations.length} {conversations.length === 1 ? "thread" : "threads"}</p>
            </div>
            <button
              className="icon-button"
              type="button"
              onClick={handleNewConversation}
              disabled={isStreaming}
              aria-label="Start a new conversation"
              title="New conversation"
            >
              +
            </button>
          </div>

          {conversationStatus === "loading" ? (
            <p className="conversation-status">Loading conversations…</p>
          ) : conversationStatus === "error" ? (
            <p className="conversation-status conversation-status-error">{loadError}</p>
          ) : conversations.length === 0 ? (
            <p className="conversation-status">Your conversations will appear here.</p>
          ) : (
            <div className="conversation-list">
              {conversations.map((conversation) => (
                <button
                  className={`conversation-item${conversation.id === activeConversationId ? " active" : ""}`}
                  key={conversation.id}
                  type="button"
                  onClick={() => {
                    if (!isStreaming) {
                      setStreamError(null);
                      setFailedTurn(null);
                      setActiveConversationId(conversation.id);
                    }
                  }}
                  disabled={isStreaming}
                >
                  <strong>{conversation.title || "Untitled conversation"}</strong>
                  <span>{formatConversationDate(conversation.created_at)}</span>
                </button>
              ))}
            </div>
          )}
        </aside>

        <section className="chat-panel" aria-label="Chat conversation">
          <header className="chat-panel-header">
            <div>
              <p className="eyebrow">Conversation</p>
              <h3>{activeConversation?.title ?? "New conversation"}</h3>
            </div>
            {isStreaming ? (
              <button className="secondary-button compact-button" type="button" onClick={handleCancel}>
                Stop generating
              </button>
            ) : null}
          </header>

          <div className="message-list" ref={messageListRef} aria-live="polite">
            {messagesStatus === "loading" ? (
              <div className="chat-empty-state"><p>Loading message history…</p></div>
            ) : messagesStatus === "error" ? (
              <div className="chat-empty-state" role="alert">
                <p>{loadError}</p>
                {activeConversationId ? (
                  <button className="secondary-button" type="button" onClick={() => void loadConversationMessages(activeConversationId)}>
                    Try again
                  </button>
                ) : null}
              </div>
            ) : messages.length === 0 ? (
              <div className="chat-empty-state">
                <span className="state-icon" aria-hidden="true">✦</span>
                <h3>What would you like to know?</h3>
                <p>Ask about the documents in {selectedWorkspace.name} to start a conversation.</p>
              </div>
            ) : (
              messages.map((message) => (
                <article className={`message-row message-${message.role.toLowerCase()}`} key={message.id}>
                  <div className="message-avatar" aria-hidden="true">
                    {message.role === "USER" ? "You" : "K"}
                  </div>
                  <div className="message-content">
                    <div className="message-meta">{message.role === "USER" ? "You" : "Assistant"}</div>
                    <div className="message-bubble">
                      {message.content ? <p>{message.content}</p> : isStreaming && message.id.startsWith("assistant-") ? <span className="typing-indicator" aria-label="Assistant is typing">● ● ●</span> : null}
                    </div>
                    {message.citations?.length ? (
                      <div className="citation-list">
                        <p className="citation-heading">Sources</p>
                        {message.citations.map((citation) => (
                          <div className="citation-card" key={citation.chunk_id}>
                            <span className="citation-icon" aria-hidden="true">↗</span>
                            <span>
                              <strong>{citation.document_name}</strong>
                              <small>{formatCitationPage(citation.page)}</small>
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </article>
              ))
            )}
          </div>

          {streamError ? (
            <div className="chat-stream-error" role="alert">
              <span>{streamError}</span>
              {failedTurn ? <button className="text-button" type="button" onClick={handleRetry}>Try again</button> : null}
            </div>
          ) : null}

          <form className="chat-composer" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="chat-message">Message</label>
            <textarea
              id="chat-message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask a question about your documents…"
              maxLength={4000}
              rows={3}
              disabled={isStreaming}
            />
            <div className="composer-footer">
              <span>{input.length}/4000 · Enter to send, Shift+Enter for a new line</span>
              <button className="primary-button compact-button" type="submit" disabled={isStreaming || !input.trim()}>
                Send
              </button>
            </div>
          </form>
        </section>
      </div>
    </section>
  );
}
