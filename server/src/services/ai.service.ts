import { env } from "../config/env.js";
import { ApiError } from "../utils/api-error.js";

export interface AiRepositoryFile {
  file_id: string;
  path: string;
  content: string;
}

const requestAi = async <T>(path: string, payload: unknown): Promise<T> => {
  if (!env.AI_SERVICE_API_KEY) throw new ApiError(503, "AI service key is not configured", "AI_SERVICE_NOT_CONFIGURED");
  let response: Response;
  try {
    response = await fetch(new URL(path, env.AI_SERVICE_URL), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.AI_SERVICE_API_KEY}` },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(90_000),
    });
  } catch {
    throw new ApiError(503, "AI service could not be reached", "AI_SERVICE_UNAVAILABLE");
  }
  const body = await response.json().catch(() => null) as { success?: boolean; data?: T; error?: { code?: string; message?: string } } | null;
  if (!response.ok || !body?.success) throw new ApiError(response.status === 401 ? 503 : response.status || 502, body?.error?.message ?? "AI service request failed", body?.error?.code ?? "AI_SERVICE_REQUEST_FAILED");
  return body.data as T;
};

export const indexRepositoryWithAi = (repositoryId: string, files: AiRepositoryFile[], replaceExisting = true) =>
  requestAi<{ repository_id: string; indexed_files: number; indexed_chunks: number; skipped_files: number }>("/api/index/repository", { repository_id: repositoryId, files, replace_existing: replaceExisting });

export const analyzeArchitectureWithAi = (repositoryId: string, files: AiRepositoryFile[]) =>
  requestAi<{ repository_id: string; nodes: unknown[]; edges: unknown[] }>("/api/architecture/analyze", { repository_id: repositoryId, files });

export const queryRepositoryWithAi = (repositoryId: string, question: string, topK?: number) =>
  requestAi<{ answer: string; sources: unknown[] }>("/api/rag/query", { repository_id: repositoryId, question, ...(topK ? { top_k: topK } : {}) });

export const analyzeIssueWithAi = (repositoryId: string, issue: { number: number; title: string; body?: string }) =>
  requestAi("/api/issues/analyze", { repository_id: repositoryId, issue });
