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

export interface AiTriagedIssue {
  number: number;
  title: string;
  body: string;
  labels: string[];
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  severity_score: number;
  category: string;
  confidence: number;
  reason: string;
  affected_subsystem: string;
  duplicate_group_id: string | null;
  is_duplicate: boolean;
  related_issues: Array<{
    number: number;
    title: string;
    similarity: number;
    relation_type: "DUPLICATE" | "RELATED" | "SIMILAR_TOPIC";
  }>;
}

export interface AiTriageSummary {
  total_issues: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  unknown_count: number;
  duplicate_groups_count: number;
  categories_breakdown: Record<string, number>;
}

export interface AiBatchTriageResult {
  repository_id: string;
  summary: AiTriageSummary;
  issues: AiTriagedIssue[];
}

export const triageIssuesWithAi = (
  repositoryId: string,
  issues: Array<{ number: number; title: string; body?: string | null; labels?: string[] }>,
  architectureComponents: string[] = []
) =>
  requestAi<AiBatchTriageResult>(
    "/api/triage/analyze",
    {
      repository_id: repositoryId,
      issues: issues.map((i) => ({
        number: i.number,
        title: i.title,
        body: i.body ?? "",
        labels: i.labels ?? [],
      })),
      architecture_components: architectureComponents,
    },
    180_000
  );

// ==========================================
// HOTSPOTS
// ==========================================
export interface AiHotspotComponent {
  name: string;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  avg_risk_score: number;
  max_risk_score: number;
  file_count: number;
  total_churn: number;
  total_bug_density: number;
}

export interface AiHotspotFile {
  id: string;
  path: string;
  name: string;
  language: string | null;
  lines_of_code: number;
  churn_score: number;
  risk_score: number;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  bug_count: number;
  component_name: string | null;
  evidence: {
    churn_commits: number;
    bug_associations: number;
    bug_fix_commits: number;
    in_degree: number;
    drivers: string[];
  };
}

export interface AiHotspotCalculationResult {
  repository_id: string;
  components: AiHotspotComponent[];
  files: AiHotspotFile[];
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
}

export const calculateHotspotsWithAi = (
  repositoryId: string,
  payload: {
    files: Array<{ id: string; path: string; name?: string; language?: string | null; lines_of_code?: number; size?: number; component?: string | null }>;
    commits: Array<{ sha: string; message: string; author?: string | null; date?: string | null; files: string[] }>;
    bug_mappings: Array<{ file_id?: string; file_path: string; issue_number?: number; score?: number }>;
    dependencies: Array<{ source_path: string; target_path: string; type?: string }>;
  }
) =>
  requestAi<AiHotspotCalculationResult>(
    "/api/hotspots/calculate",
    {
      repository_id: repositoryId,
      ...payload,
    },
    60_000
  );

// ==========================================
// AUTO README GENERATOR
// ==========================================
export interface AiReadmeResult {
  repository_id: string;
  project_name: string;
  tagline: string;
  overview: string;
  architecture_summary: string;
  tech_stack: Array<{ category: string; name: string }>;
  quick_start: {
    prerequisites: string[];
    installation: string[];
    environment_variables: Array<{ key: string; description: string; default?: string }>;
    run_commands: Array<{ label: string; command: string }>;
  };
  key_modules: Array<{ path: string; role: string }>;
  markdown: string;
  existing_readme?: string | null;
}

export const generateReadmeWithAi = (
  repositoryId: string,
  payload: {
    repository_name: string;
    owner: string;
    description?: string | null;
    primary_language?: string | null;
    files: Array<{ path: string; content: string }>;
    architecture_summary?: string | null;
    existing_readme?: string | null;
  }
) =>
  requestAi<AiReadmeResult>(
    "/api/readme/generate",
    {
      repository_id: repositoryId,
      ...payload,
    },
    90_000
  );




