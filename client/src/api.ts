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

export interface ArchitectureComponent {
  id: string;
  name: string;
  type: string;
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
  description?: string | null;
}

export interface SemanticArchitecture {
  title: string;
  summary: string;
  architecture_style?: string;
  entry_points?: string[];
  components: ArchitectureComponent[];
  relationships: ArchitectureRelationship[];
  flows?: ExecutionFlow[];
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
