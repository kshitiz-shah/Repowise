export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:3000/api";

export interface ApiError { code: string; message: string }
interface Envelope<T> { success: boolean; data?: T; error?: ApiError }

export interface User { id: string; name: string; email: string }
export interface Session { user: User; accessToken: string }
export interface Repository { id: string; name: string; githubOwner: string; githubUrl: string; description: string | null; defaultBranch: string | null; primaryLanguage: string | null }
export interface GraphNode {
  id: string;
  label: string;
  type: "folder" | "file";
  language?: string | null;
  path?: string | null;
  children_count?: number | null;
  lines_of_code?: number | null;
}
export interface GraphEdge {
  source: string;
  target: string;
  type: "CONTAINS" | "IMPORTS";
}
export interface ArchitectureStatistics {
  files: number;
  folders: number;
  dependencies: number;
}
export interface InternalFlowStep {
  from_symbol: string;
  to_symbol: string;
  action: string;
  file_path?: string | null;
}

export interface ExecutionFlowStep {
  component: string;
  action: string;
  file?: string | null;
  symbol?: string | null;
}

export interface ExecutionFlow {
  name: string;
  description: string;
  steps: ExecutionFlowStep[];
}

export interface ComponentEvidence {
  files?: string[];
  symbols?: string[];
  imports?: string[];
  routes?: string[];
  keywords?: string[];
}

export interface ArchitectureGroup {
  id: string;
  label: string;
  description?: string;
}

export interface ArchitectureComponent {
  id: string;
  name: string;
  type: string;
  shape?: "box" | "database" | "circle" | "queue" | "hexagon" | "document";
  group_id?: string;
  groupId?: string;
  group_label?: string;
  description: string;
  responsibilities?: string[];
  files?: string[];
  symbols?: string[];
  routes?: string[];
  internal_flow?: InternalFlowStep[];
  evidence?: ComponentEvidence;
}

export interface ArchitectureRelationship {
  source: string;
  target: string;
  type: string;
  label: string;
  style?: "solid" | "dashed";
  description?: string | null;
}

export interface SemanticArchitecture {
  title: string;
  summary: string;
  architecture_style?: string;
  entry_points?: string[];
  groups?: ArchitectureGroup[];
  components: ArchitectureComponent[];
  relationships: ArchitectureRelationship[];
  flows?: ExecutionFlow[];
  mermaid_code?: string;
}


export interface Architecture {
  repository_id: string;
  architecture?: SemanticArchitecture;
  nodes: GraphNode[];
  edges: GraphEdge[];
  statistics?: ArchitectureStatistics;
}
export interface Source { file_id: string; file_path: string; start_line: number; end_line: number; score: number }
export interface Answer { answer: string; sources: Source[] }

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  const body = await response.json().catch(() => null) as Envelope<T> | null;
  if (!response.ok || !body?.success || body.data === undefined) throw new Error(body?.error?.message ?? "The request failed. Please try again.");
  return body.data;
}

export const signUp = (payload: { name: string; email: string; password: string }) => request<Session>("/auth/register", { method: "POST", body: JSON.stringify(payload) });
export const signIn = (payload: { email: string; password: string }) => request<Session>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
export const repositories = (token: string) => request<Repository[]>("/repositories", {}, token);
export const addRepository = (token: string, githubUrl: string) => request<Repository>("/repositories", { method: "POST", body: JSON.stringify({ githubUrl }) }, token);
export const indexRepository = (token: string, id: string) => request<{ indexed_files: number; indexed_chunks: number }>(`/repositories/${id}/index`, { method: "POST", body: "{}" }, token);
export const architecture = (token: string, id: string) => request<Architecture>(`/repositories/${id}/architecture`, { method: "POST", body: "{}" }, token);
export const askQuestion = (token: string, id: string, question: string) => request<Answer>(`/repositories/${id}/query`, { method: "POST", body: JSON.stringify({ question, topK: 8 }) }, token);

export interface BugLocalizationSignals {
  semantic_similarity: number;
  keyword_score: number;
  dependency_score: number;
  path_score: number;
  historical_score: number;
}

export interface RelevantChunk {
  start_line: number;
  end_line: number;
  symbol: string | null;
  chunk_type: string;
  score: number;
}

export interface FileCandidateEvidence {
  matched_keywords: string[];
  matched_symbols: string[];
  dependency_chain: string[];
  relevant_chunks: RelevantChunk[];
}

export interface FileCandidate {
  file_path: string;
  file_id: string;
  final_score: number;
  confidence: number;
  rank: number;
  signals: BugLocalizationSignals;
  evidence: FileCandidateEvidence;
  explanation: string | null;
}

export interface IssueAnalysis {
  problem_summary: string;
  error_messages: string[];
  entities: string[];
  file_path_hints: string[];
  api_endpoints: string[];
  domain_concepts: string[];
  affected_subsystem: string;
  search_queries: string[];
}

export interface BugLocalizationResult {
  repository_id: string;
  issue_analysis: IssueAnalysis;
  candidates: FileCandidate[];
  total_files_analyzed: number;
  analysis_summary: string;
}

export interface GitHubIssueDetails {
  number: number;
  title: string;
  body: string | null;
  state: string;
  author: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export const localizeBug = (
  token: string,
  id: string,
  issue: { number: number; title: string; body?: string; topK?: number; includeExplanation?: boolean }
) =>
  request<BugLocalizationResult>(
    `/repositories/${id}/bugs/localize`,
    { method: "POST", body: JSON.stringify(issue) },
    token
  );

export const fetchGitHubIssue = (token: string, id: string, issueNumber: number) =>
  request<GitHubIssueDetails>(`/repositories/${id}/bugs/github-issue/${issueNumber}`, {}, token);

export const getBugMappingsHistory = (token: string, id: string) =>
  request<unknown[]>(`/repositories/${id}/bugs/history`, {}, token);

// ==========================================
// BUG TRIAGE BOARD
// ==========================================
export interface IssueFileMappingSummary {
  id: string;
  rank: number;
  score: number;
  confidence: number;
  file: {
    path: string;
    name: string;
    language: string | null;
  };
}

export interface IssueItem {
  id: string;
  githubIssueId: string;
  number: number;
  title: string;
  body: string | null;
  state: string;
  labels: string[];
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN" | null;
  category: string | null;
  triageReason: string | null;
  triageConfidence: number | null;
  relatedIssueIds: number[];
  author: string | null;
  githubCreatedAt: string | null;
  githubUpdatedAt: string | null;
  fileMappings?: IssueFileMappingSummary[];
}

export interface TriageSummary {
  total_issues: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  unknown_count: number;
  duplicate_groups_count: number;
  categories_breakdown: Record<string, number>;
}

export interface TriageDataResponse {
  summary: TriageSummary;
  issues: IssueItem[];
  triaged_details?: Array<{
    number: number;
    title: string;
    severity: string;
    category: string;
    reason: string;
    affected_subsystem: string;
    is_duplicate: boolean;
    related_issues: Array<{
      number: number;
      title: string;
      similarity: number;
      relation_type: string;
    }>;
  }>;
}

export const syncIssues = (token: string, id: string) =>
  request<{ synced_count: number; issues: IssueItem[] }>(`/repositories/${id}/issues/sync`, { method: "POST", body: "{}" }, token);

export const getIssues = (token: string, id: string) =>
  request<IssueItem[]>(`/repositories/${id}/issues`, {}, token);

export const triageIssues = (token: string, id: string) =>
  request<TriageDataResponse>(`/repositories/${id}/triage`, { method: "POST", body: "{}" }, token);

export const getTriageData = (token: string, id: string) =>
  request<TriageDataResponse>(`/repositories/${id}/triage`, {}, token);

// ==========================================
// HOTSPOT DETECTOR
// ==========================================
export interface HotspotComponentRisk {
  name: string;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  avg_risk_score: number;
  file_count: number;
  total_churn: number;
  total_bug_density: number;
}

export interface HotspotFileItem {
  id: string;
  path: string;
  name: string;
  language: string | null;
  linesOfCode: number | null;
  churnScore: number | null;
  riskScore: number | null;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  bugCount: number;
  componentName: string | null;
  evidence?: {
    churn_commits: number;
    bug_associations: number;
    bug_fix_commits: number;
    in_degree: number;
    drivers: string[];
  };
}

export interface HotspotAnalysisResponse {
  repository_id: string;
  components: HotspotComponentRisk[];
  files: HotspotFileItem[];
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
}

export const getHotspots = (token: string, id: string) =>
  request<HotspotAnalysisResponse>(`/repositories/${id}/hotspots`, {}, token);

export const calculateHotspots = (token: string, id: string) =>
  request<HotspotAnalysisResponse>(`/repositories/${id}/hotspots/calculate`, { method: "POST", body: "{}" }, token);

// ==========================================
// AUTO README GENERATOR
// ==========================================
export interface AutoReadmeResult {
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

export const generateReadme = (token: string, id: string) =>
  request<AutoReadmeResult>(`/repositories/${id}/readme/generate`, { method: "POST", body: "{}" }, token);

export const getReadme = (token: string, id: string) =>
  request<AutoReadmeResult | { existing_readme: string | null }>(`/repositories/${id}/readme`, {}, token);


