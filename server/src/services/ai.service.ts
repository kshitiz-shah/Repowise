import { env } from "../config/env.js";
import { ApiError } from "../utils/api-error.js";

export interface AiRepositoryFile {
  file_id: string;
  path: string;
  content: string;
}

const requestAi = async <T>(path: string, payload: unknown, timeoutMs = 90_000): Promise<T> => {
  if (!env.AI_SERVICE_API_KEY) throw new ApiError(503, "AI service key is not configured", "AI_SERVICE_NOT_CONFIGURED");
  let response: Response;
  try {
    response = await fetch(new URL(path, env.AI_SERVICE_URL), {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.AI_SERVICE_API_KEY}` },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new ApiError(503, "AI service could not be reached", "AI_SERVICE_UNAVAILABLE");
  }
  const body = (await response.json().catch(() => null)) as {
    success?: boolean;
    data?: T;
    error?: { code?: string; message?: string };
  } | null;
  if (!response.ok || !body?.success) {
    throw new ApiError(
      response.status === 401 ? 503 : response.status || 502,
      body?.error?.message ?? "AI service request failed",
      body?.error?.code ?? "AI_SERVICE_REQUEST_FAILED"
    );
  }
  return body.data as T;
};

export const indexRepositoryWithAi = (repositoryId: string, files: AiRepositoryFile[], replaceExisting = true) =>
  requestAi<{ repository_id: string; indexed_files: number; indexed_chunks: number; skipped_files: number }>("/api/index/repository", { repository_id: repositoryId, files, replace_existing: replaceExisting });

export const analyzeArchitectureWithAi = (repositoryId: string, files: AiRepositoryFile[]) =>
  requestAi<{ repository_id: string; architecture?: unknown; nodes: unknown[]; edges: unknown[]; statistics: { files: number; folders: number; dependencies: number } }>("/api/architecture/analyze", { repository_id: repositoryId, files });

export const queryRepositoryWithAi = (repositoryId: string, question: string, files?: AiRepositoryFile[], topK?: number) =>
  requestAi<{ answer: string; sources: unknown[] }>("/api/rag/query", {
    repository_id: repositoryId,
    question,
    ...(files && files.length > 0 ? { files } : {}),
    ...(topK ? { top_k: topK } : {}),
  });

export const analyzeIssueWithAi = (repositoryId: string, issue: { number: number; title: string; body?: string }) =>
  requestAi("/api/issues/analyze", { repository_id: repositoryId, issue });

export interface AiFileCandidateSignals {
  semantic_similarity: number;
  keyword_score: number;
  dependency_score: number;
  path_score: number;
  historical_score: number;
}

export interface AiRelevantChunk {
  start_line: number;
  end_line: number;
  symbol: string | null;
  chunk_type: string;
  score: number;
}

export interface AiFileCandidateEvidence {
  matched_keywords: string[];
  matched_symbols: string[];
  dependency_chain: string[];
  relevant_chunks: AiRelevantChunk[];
}

export interface AiFileCandidate {
  file_path: string;
  file_id: string;
  final_score: number;
  confidence: number;
  rank: number;
  signals: AiFileCandidateSignals;
  evidence: AiFileCandidateEvidence;
  explanation: string | null;
}

export interface AiIssueAnalysis {
  problem_summary: string;
  error_messages: string[];
  entities: string[];
  file_path_hints: string[];
  api_endpoints: string[];
  domain_concepts: string[];
  affected_subsystem: string;
  search_queries: string[];
}

export interface AiBugLocalizationResult {
  repository_id: string;
  issue_analysis: AiIssueAnalysis;
  candidates: AiFileCandidate[];
  total_files_analyzed: number;
  analysis_summary: string;
}

export const localizeBugWithAi = (
  repositoryId: string,
  issue: { number: number; title: string; body?: string },
  files: AiRepositoryFile[],
  commitHistory?: unknown[],
  topK = 5,
  includeExplanation = true
) =>
  requestAi<AiBugLocalizationResult>(
    "/api/bugs/localize",
    {
      repository_id: repositoryId,
      issue,
      files,
      commit_history: commitHistory ?? [],
      top_k: topK,
      include_explanation: includeExplanation,
    },
    180_000
  );

