import { env } from "../config/env.js";
import { ApiError } from "../utils/api-error.js";

export interface GitHubRepositoryReference {
  owner: string;
  name: string;
  canonicalUrl: string;
}

export interface GitHubRepositoryMetadata extends GitHubRepositoryReference {
  description: string | null;
  defaultBranch: string | null;
  primaryLanguage: string | null;
}

export interface GitHubSourceFile {
  path: string;
  content: string;
  size: number;
}

const sourceExtensions = new Set([".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".cs", ".c", ".h", ".cpp"]);
const maxFiles = 100;
const maxFileSizeBytes = 300_000;

const githubHeaders = (accept = "application/vnd.github+json") => ({
  Accept: accept,
  "User-Agent": "RepoWise",
  ...(env.GITHUB_TOKEN ? { Authorization: `Bearer ${env.GITHUB_TOKEN}` } : {}),
});

export const parseRepositoryUrl = (value: string): GitHubRepositoryReference => {
  let url: URL;
  try { url = new URL(value); } catch { throw new ApiError(400, "A valid GitHub repository URL is required", "INVALID_GITHUB_URL"); }

  const parts = url.pathname.replace(/^\/+|\/+$/g, "").replace(/\.git$/, "").split("/");
  if (url.protocol !== "https:" || url.hostname.toLowerCase() !== "github.com" || parts.length !== 2 || !parts.every(Boolean)) {
    throw new ApiError(400, "URL must be an HTTPS GitHub repository URL", "INVALID_GITHUB_URL");
  }
  const [owner, name] = parts;
  return { owner, name, canonicalUrl: `https://github.com/${owner}/${name}` };
};

export const getRepositoryMetadata = async (githubUrl: string): Promise<GitHubRepositoryMetadata> => {
  const reference = parseRepositoryUrl(githubUrl);
  let response: Response;
  try {
    response = await fetch(`${env.GITHUB_API_URL}/repos/${encodeURIComponent(reference.owner)}/${encodeURIComponent(reference.name)}`, {
      headers: githubHeaders(),
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    throw new ApiError(502, "GitHub could not be reached", "GITHUB_UNAVAILABLE");
  }
  if (response.status === 404) throw new ApiError(404, "GitHub repository not found or is not public", "GITHUB_REPOSITORY_NOT_FOUND");
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null) as { message?: string } | null;
    if (response.status === 403 && errorBody?.message?.includes("rate limit")) {
      throw new ApiError(429, "GitHub API rate limit exceeded. Add a GITHUB_TOKEN to server/.env to increase the rate limit.", "GITHUB_RATE_LIMITED");
    }
    throw new ApiError(502, errorBody?.message ? `GitHub metadata request failed: ${errorBody.message}` : "GitHub metadata request failed", "GITHUB_REQUEST_FAILED");
  }

  const data = await response.json() as { description: string | null; default_branch: string | null; language: string | null };
  return { ...reference, description: data.description, defaultBranch: data.default_branch, primaryLanguage: data.language };
};

export const getRepositorySourceFiles = async (repository: Pick<GitHubRepositoryReference, "owner" | "name"> & { defaultBranch: string | null }): Promise<GitHubSourceFile[]> => {
  const branch = repository.defaultBranch ?? "HEAD";
  let treeResponse: Response;
  try {
    treeResponse = await fetch(`${env.GITHUB_API_URL}/repos/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/git/trees/${encodeURIComponent(branch)}?recursive=1`, {
      headers: githubHeaders(), signal: AbortSignal.timeout(20_000),
    });
  } catch {
    throw new ApiError(502, "GitHub could not be reached", "GITHUB_UNAVAILABLE");
  }
  if (!treeResponse.ok) {
    const errorBody = await treeResponse.json().catch(() => null) as { message?: string } | null;
    if (treeResponse.status === 403 && errorBody?.message?.includes("rate limit")) {
      throw new ApiError(429, "GitHub API rate limit exceeded. Add a GITHUB_TOKEN to server/.env to increase the rate limit.", "GITHUB_RATE_LIMITED");
    }
    throw new ApiError(502, errorBody?.message ? `GitHub source tree request failed: ${errorBody.message}` : "GitHub source tree request failed", "GITHUB_REQUEST_FAILED");
  }
  const tree = await treeResponse.json() as { truncated?: boolean; tree?: Array<{ path: string; type: string; size?: number }> };
  if (tree.truncated) throw new ApiError(422, "Repository is too large to analyze through the GitHub tree API", "REPOSITORY_TOO_LARGE");
  const candidates = (tree.tree ?? []).filter((item) => item.type === "blob" && item.size !== undefined && item.size <= maxFileSizeBytes && sourceExtensions.has(item.path.slice(item.path.lastIndexOf(".")).toLowerCase())).slice(0, maxFiles);
  if (!candidates.length) throw new ApiError(422, "No supported source files were found in this repository", "NO_SUPPORTED_SOURCE_FILES");

  const results = await Promise.all(candidates.map(async (file): Promise<GitHubSourceFile | null> => {
    try {
      const response = await fetch(`${env.GITHUB_API_URL}/repos/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}/contents/${file.path.split("/").map(encodeURIComponent).join("/")}?ref=${encodeURIComponent(branch)}`, {
        headers: githubHeaders("application/vnd.github.raw+json"), signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) return null;
      return { path: file.path, content: await response.text(), size: file.size! };
    } catch { return null; }
  }));
  const files = results.filter((file): file is GitHubSourceFile => file !== null && file.content.length > 0);
  if (!files.length) throw new ApiError(502, "GitHub source files could not be read", "GITHUB_REQUEST_FAILED");
  return files;
};
