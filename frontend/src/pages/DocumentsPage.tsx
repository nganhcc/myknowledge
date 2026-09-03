import { useEffect, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import {
  deleteDocument,
  getDocumentStatus,
  listDocuments,
  uploadDocument,
} from "../api/documents";
import { useAuth } from "../auth/useAuth";
import type { DocumentResponse, DocumentStatus } from "../types/api";
import { useWorkspace } from "../workspaces/useWorkspace";

type LoadStatus = "loading" | "ready" | "error";

const statusLabels: Record<DocumentStatus, string> = {
  PENDING: "Pending",
  PROCESSING: "Processing",
  READY: "Ready",
  FAILED: "Failed",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(date: string): string {
  return new Date(date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function errorMessage(caught: unknown, fallback: string): string {
  if (caught instanceof ApiError) {
    if (caught.status === 409) return "This document has already been uploaded.";
    return caught.message;
  }
  return caught instanceof Error ? caught.message : fallback;
}

function isProcessing(status: DocumentStatus): boolean {
  return status === "PENDING" || status === "PROCESSING";
}

export function DocumentsPage() {
  const { selectedWorkspaceId, selectedWorkspace } = useWorkspace();
  const { signOut } = useAuth();
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loadStatus, setLoadStatus] = useState<LoadStatus>("ready");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setDocuments([]);
      setLoadError(null);
      setLoadStatus("ready");
      return;
    }

    let cancelled = false;
    setLoadStatus("loading");
    setLoadError(null);
    setActionError(null);

    void listDocuments(selectedWorkspaceId)
      .then((nextDocuments) => {
        if (cancelled) return;
        setDocuments(nextDocuments);
        setLoadStatus("ready");
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        if (caught instanceof ApiError && caught.kind === "unauthorized") {
          signOut();
          return;
        }
        setLoadError(errorMessage(caught, "Unable to load documents."));
        setLoadStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [selectedWorkspaceId, signOut]);

  useEffect(() => {
    if (!selectedWorkspaceId || !documents.some((document) => isProcessing(document.status))) {
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      const processingDocuments = documents.filter((document) => isProcessing(document.status));
      void Promise.all(
        processingDocuments.map((document) =>
          getDocumentStatus(selectedWorkspaceId, document.id),
        ),
      )
        .then((updates) => {
          if (cancelled) return;
          setDocuments((currentDocuments) =>
            currentDocuments.map((document) => {
              const update = updates.find((item) => item.id === document.id);
              if (!update || update.status === document.status) return document;
              return { ...document, status: update.status };
            }),
          );
        })
        .catch((caught: unknown) => {
          if (cancelled) return;
          if (caught instanceof ApiError && caught.kind === "unauthorized") {
            signOut();
            return;
          }
          setActionError(errorMessage(caught, "Unable to refresh document status."));
        });
    }, 2500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [documents, selectedWorkspaceId, signOut]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !selectedWorkspaceId) return;

    setIsUploading(true);
    setActionError(null);
    try {
      const document = await uploadDocument(selectedWorkspaceId, file);
      setDocuments((currentDocuments) => [document, ...currentDocuments]);
    } catch (caught) {
      if (caught instanceof ApiError && caught.kind === "unauthorized") {
        signOut();
        return;
      }
      setActionError(errorMessage(caught, "Unable to upload the document."));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDelete(document: DocumentResponse) {
    if (!selectedWorkspaceId) return;
    if (!window.confirm(`Delete “${document.filename}”? This cannot be undone.`)) return;

    setDeletingDocumentId(document.id);
    setActionError(null);
    try {
      await deleteDocument(selectedWorkspaceId, document.id);
      setDocuments((currentDocuments) =>
        currentDocuments.filter((item) => item.id !== document.id),
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.kind === "unauthorized") {
        signOut();
        return;
      }
      setActionError(errorMessage(caught, "Unable to delete the document."));
    } finally {
      setDeletingDocumentId(null);
    }
  }

  if (!selectedWorkspaceId || !selectedWorkspace) {
    return (
      <section className="state-card" aria-labelledby="documents-empty-workspace-title">
        <span className="state-icon" aria-hidden="true">▤</span>
        <h2 id="documents-empty-workspace-title">Create a workspace first</h2>
        <p>Documents belong to a workspace, so create one before adding your knowledge base.</p>
        <Link className="primary-button" to="/workspaces">Go to workspaces</Link>
      </section>
    );
  }

  return (
    <section className="documents-page" aria-labelledby="documents-page-title">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{selectedWorkspace.name}</p>
          <h2 id="documents-page-title">Documents</h2>
          <p className="page-description">
            Upload source material for your workspace and we’ll prepare it for questions.
          </p>
        </div>
        <label className="primary-button upload-button">
          {isUploading ? "Uploading…" : "Upload document"}
          <input
            className="file-input"
            type="file"
            onChange={(event) => void handleUpload(event)}
            disabled={isUploading}
          />
        </label>
      </div>

      {actionError ? <div className="form-error" role="alert">{actionError}</div> : null}

      {loadStatus === "error" ? (
        <div className="state-card" role="alert">
          <span className="state-icon">!</span>
          <h2>We couldn’t load your documents</h2>
          <p>{loadError}</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => {
              setLoadStatus("loading");
              setLoadError(null);
              setDocuments([]);
              // Changing the selected workspace is not required; reload the page-level data.
              void listDocuments(selectedWorkspaceId)
                .then((nextDocuments) => {
                  setDocuments(nextDocuments);
                  setLoadStatus("ready");
                })
                .catch((caught: unknown) => {
                  if (caught instanceof ApiError && caught.kind === "unauthorized") {
                    signOut();
                    return;
                  }
                  setLoadError(errorMessage(caught, "Unable to load documents."));
                  setLoadStatus("error");
                });
            }}
          >
            Try again
          </button>
        </div>
      ) : loadStatus === "loading" ? (
        <div className="state-card" aria-live="polite">
          <span className="state-icon" aria-hidden="true">…</span>
          <h2>Loading documents</h2>
          <p>Fetching the documents in {selectedWorkspace.name}.</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="state-card">
          <span className="state-icon" aria-hidden="true">▤</span>
          <h2>Your knowledge base is empty</h2>
          <p>Upload a document to give your workspace something to search and answer from.</p>
          <label className="primary-button upload-button">
            Upload your first document
            <input
              className="file-input"
              type="file"
              onChange={(event) => void handleUpload(event)}
              disabled={isUploading}
            />
          </label>
        </div>
      ) : (
        <div className="document-list-card">
          <div className="document-list-header" aria-hidden="true">
            <span>Document</span>
            <span>Status</span>
            <span>Added</span>
            <span />
          </div>
          <div className="document-list" aria-live="polite">
            {documents.map((document) => (
              <article className="document-row" key={document.id}>
                <div className="document-main">
                  <span className="document-icon" aria-hidden="true">▤</span>
                  <div>
                    <strong>{document.title || document.filename}</strong>
                    <span>{document.filename} · {formatFileSize(document.size)}</span>
                  </div>
                </div>
                <span className={`document-status status-${document.status.toLowerCase()}`}>
                  {statusLabels[document.status]}
                </span>
                <span className="document-date">{formatDate(document.created_at)}</span>
                <button
                  className="danger-button document-delete"
                  type="button"
                  onClick={() => void handleDelete(document)}
                  disabled={deletingDocumentId === document.id}
                >
                  {deletingDocumentId === document.id ? "Deleting…" : "Delete"}
                </button>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
