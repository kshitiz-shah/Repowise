import { useEffect, useMemo, useState } from "react";
import * as api from "../api";
import type { IssueItem, Repository, TriageSummary } from "../api";
import "./BugTriageBoard.css";

interface BugTriageBoardProps {
  repository: Repository;
  token: string;
  run: (label: string, action: () => Promise<void>) => Promise<void>;
  loading: string | null;
  onSelectIssueForMapping?: (issue: { number: number; title: string; body?: string | null }) => void;
}

export function BugTriageBoard({
  repository,
  token,
  run,
  loading,
  onSelectIssueForMapping,
}: BugTriageBoardProps) {
  const storageKey = `repowise_triage_${repository.id}`;
  const [issues, setIssues] = useState<IssueItem[]>(() => {
    try {
      const cached = sessionStorage.getItem(`${storageKey}_issues`);
      return cached ? (JSON.parse(cached) as IssueItem[]) : [];
    } catch {
      return [];
    }
  });
  const [summary, setSummary] = useState<TriageSummary | null>(() => {
    try {
      const cached = sessionStorage.getItem(`${storageKey}_summary`);
      return cached ? (JSON.parse(cached) as TriageSummary) : null;
    } catch {
      return null;
    }
  });
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [onlyDuplicates, setOnlyDuplicates] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Load issues and triage summary on repository change
  useEffect(() => {
    let isMounted = true;
    setStatusMessage(null);
    void api.getTriageData(token, repository.id)
      .then((res) => {
        if (!isMounted) return;
        setIssues(res.issues);
        setSummary(res.summary);
        try {
          sessionStorage.setItem(`${storageKey}_issues`, JSON.stringify(res.issues));
          sessionStorage.setItem(`${storageKey}_summary`, JSON.stringify(res.summary));
        } catch {}
      })
      .catch((err) => {
        console.warn("Could not load initial triage data:", err);
      });

    return () => {
      isMounted = false;
    };
  }, [repository.id, token, storageKey]);

  const handleSyncIssues = async () => {
    setStatusMessage(null);
    await run("sync-issues", async () => {
      const res = await api.syncIssues(token, repository.id);
      setStatusMessage(`Synced ${res.synced_count} open issues from GitHub.`);
      // Reload triage data
      const triageRes = await api.getTriageData(token, repository.id);
      setIssues(triageRes.issues);
      setSummary(triageRes.summary);
      try {
        sessionStorage.setItem(`${storageKey}_issues`, JSON.stringify(triageRes.issues));
        sessionStorage.setItem(`${storageKey}_summary`, JSON.stringify(triageRes.summary));
      } catch {}
    });
  };

  const handleRunTriage = async () => {
    setStatusMessage(null);
    await run("run-triage", async () => {
      const res = await api.triageIssues(token, repository.id);
      setIssues(res.issues);
      setSummary(res.summary);
      try {
        sessionStorage.setItem(`${storageKey}_issues`, JSON.stringify(res.issues));
        sessionStorage.setItem(`${storageKey}_summary`, JSON.stringify(res.summary));
      } catch {}
      setStatusMessage(`Successfully triaged ${res.issues.length} issues using AI analysis & semantic clustering.`);
    });
  };

  // Filtered issues calculation
  const filteredIssues = useMemo(() => {
    return issues.filter((issue) => {
      // Severity filter
      if (selectedSeverity !== "ALL") {
        if (selectedSeverity === "UNKNOWN") {
          if (issue.severity && issue.severity !== "UNKNOWN") return false;
        } else if (issue.severity !== selectedSeverity) {
          return false;
        }
      }

      // Category filter
      if (selectedCategory !== "ALL") {
        if (!issue.category || issue.category.toLowerCase() !== selectedCategory.toLowerCase()) {
          return false;
        }
      }

      // Duplicates only filter
      if (onlyDuplicates) {
        const hasRelated = Array.isArray(issue.relatedIssueIds) && issue.relatedIssueIds.length > 0;
        if (!hasRelated) return false;
      }

      // Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesNum = String(issue.number).includes(q);
        const matchesTitle = issue.title.toLowerCase().includes(q);
        const matchesBody = (issue.body || "").toLowerCase().includes(q);
        const matchesReason = (issue.triageReason || "").toLowerCase().includes(q);
        if (!matchesNum && !matchesTitle && !matchesBody && !matchesReason) return false;
      }

      return true;
    });
  }, [issues, selectedSeverity, selectedCategory, onlyDuplicates, searchQuery]);

  const categories = useMemo(() => {
    if (!summary?.categories_breakdown) return [];
    return Object.keys(summary.categories_breakdown);
  }, [summary]);

  return (
    <div className="triage-container">
      {/* Overview Stat Cards */}
      <div className="triage-header-stats">
        <div className="triage-stat-card">
          <span className="triage-stat-label">Total Open</span>
          <span className="triage-stat-value">{summary?.total_issues ?? issues.length}</span>
        </div>
        <div className="triage-stat-card critical">
          <span className="triage-stat-label">Critical</span>
          <span className="triage-stat-value">{summary?.critical_count ?? 0}</span>
        </div>
        <div className="triage-stat-card high">
          <span className="triage-stat-label">High Priority</span>
          <span className="triage-stat-value">{summary?.high_count ?? 0}</span>
        </div>
        <div className="triage-stat-card medium">
          <span className="triage-stat-label">Medium</span>
          <span className="triage-stat-value">{summary?.medium_count ?? 0}</span>
        </div>
        <div className="triage-stat-card low">
          <span className="triage-stat-label">Low</span>
          <span className="triage-stat-value">{summary?.low_count ?? 0}</span>
        </div>
        <div className="triage-stat-card duplicates">
          <span className="triage-stat-label">Related / Dups</span>
          <span className="triage-stat-value">{summary?.duplicate_groups_count ?? 0}</span>
        </div>
      </div>

      {/* Toolbar: Search, Filters & Action Buttons */}
      <div className="triage-toolbar">
        <div className="triage-search-box">
          <input
            type="text"
            className="triage-search-input"
            placeholder="Search issues by title, #id, or explanation..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="triage-filters">
          <button
            type="button"
            className={`triage-pill ${selectedSeverity === "ALL" ? "active" : ""}`}
            onClick={() => setSelectedSeverity("ALL")}
          >
            All Severities
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedSeverity === "CRITICAL" ? "active" : ""}`}
            onClick={() => setSelectedSeverity("CRITICAL")}
          >
            Critical
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedSeverity === "HIGH" ? "active" : ""}`}
            onClick={() => setSelectedSeverity("HIGH")}
          >
            High
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedSeverity === "MEDIUM" ? "active" : ""}`}
            onClick={() => setSelectedSeverity("MEDIUM")}
          >
            Medium
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedSeverity === "LOW" ? "active" : ""}`}
            onClick={() => setSelectedSeverity("LOW")}
          >
            Low
          </button>

          {categories.length > 0 && (
            <select
              className="triage-pill"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{ padding: "0.35rem 0.65rem" }}
            >
              <option value="ALL">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat} ({summary?.categories_breakdown[cat]})
                </option>
              ))}
            </select>
          )}

          <button
            type="button"
            className={`triage-pill ${onlyDuplicates ? "active" : ""}`}
            onClick={() => setOnlyDuplicates((v) => !v)}
          >
            👯 Duplicates Only
          </button>
        </div>

        <div className="triage-actions">
          <button
            type="button"
            className="triage-btn triage-btn-secondary"
            onClick={handleSyncIssues}
            disabled={loading !== null}
          >
            {loading === "sync-issues" ? "Syncing GitHub…" : "🔄 Sync GitHub Issues"}
          </button>
          <button
            type="button"
            className="triage-btn triage-btn-primary"
            onClick={handleRunTriage}
            disabled={loading !== null}
          >
            {loading === "run-triage" ? "AI Triaging…" : "⚡ Run AI Triage"}
          </button>
        </div>
      </div>

      {statusMessage && (
        <div style={{ padding: "0.6rem 0.9rem", background: "#f0fdf4", border: "1px solid #bbf7d0", color: "#166534", borderRadius: "6px", fontSize: "0.85rem" }}>
          {statusMessage}
        </div>
      )}

      {/* Issues List */}
      {filteredIssues.length === 0 ? (
        <div className="triage-empty-state">
          <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📋</div>
          <h4>No issues found matching criteria</h4>
          <p>
            {issues.length === 0
              ? "No open GitHub issues have been synced yet. Click “Sync GitHub Issues” to fetch open issues from the repository."
              : "Try adjusting your search query or severity filters to view more issues."}
          </p>
          {issues.length === 0 && (
            <button
              type="button"
              className="triage-btn triage-btn-primary"
              onClick={handleSyncIssues}
              disabled={loading !== null}
            >
              🔄 Sync GitHub Issues Now
            </button>
          )}
        </div>
      ) : (
        <div className="triage-list">
          {filteredIssues.map((issue) => {
            const severityClass = issue.severity ? `severity-${issue.severity.toLowerCase()}` : "severity-unknown";
            const borderClass = issue.severity ? `${issue.severity.toLowerCase()}-border` : "";
            const hasRelated = Array.isArray(issue.relatedIssueIds) && issue.relatedIssueIds.length > 0;
            const topMappings = issue.fileMappings || [];

            return (
              <div key={issue.id} className={`triage-card ${borderClass}`}>
                <div className="triage-card-header">
                  <div className="triage-card-title-group">
                    <div>
                      <span className="triage-issue-num">#{issue.number}</span>
                      <a
                        href={`${repository.githubUrl}/issues/${issue.number}`}
                        target="_blank"
                        rel="noreferrer"
                        className="triage-issue-title"
                      >
                        {issue.title}
                      </a>
                    </div>
                    <div className="triage-meta-row">
                      {issue.author && <span>by @{issue.author}</span>}
                      {issue.githubCreatedAt && (
                        <span>opened {new Date(issue.githubCreatedAt).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>

                  <div className="triage-badges-row">
                    <span className={`severity-badge ${severityClass}`}>
                      {issue.severity || "UNKNOWN"}
                    </span>
                    {issue.category && (
                      <span className="category-badge">{issue.category}</span>
                    )}
                    {issue.triageConfidence !== null && issue.triageConfidence !== undefined && (
                      <span className="confidence-badge">
                        {Math.round(issue.triageConfidence * 100)}% conf
                      </span>
                    )}
                  </div>
                </div>

                {/* Duplicate / Related cluster banner */}
                {hasRelated && (
                  <div className="duplicate-alert-banner">
                    <span>👯 <strong>Semantic Cluster Match:</strong> Potential duplicate or closely related to:</span>
                    <div className="related-issues-list">
                      {issue.relatedIssueIds.map((relNum) => (
                        <a
                          key={relNum}
                          href={`${repository.githubUrl}/issues/${relNum}`}
                          target="_blank"
                          rel="noreferrer"
                          className="related-issue-chip"
                        >
                          #{relNum}
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Rationale / Explanation */}
                {issue.triageReason && (
                  <div className="triage-reason-box">
                    <strong>Triage Rationale: </strong>
                    {issue.triageReason}
                  </div>
                )}

                {/* Candidate Responsible Files (if previously mapped) */}
                {topMappings.length > 0 && (
                  <div className="triage-mapped-files">
                    <div className="triage-mapped-files-header">
                      🎯 Identified Suspect Files (from Bug Mapping)
                    </div>
                    <div className="triage-mapped-files-list">
                      {topMappings.map((m) => (
                        <div key={m.id} className="triage-file-item">
                          <span className="triage-file-path">
                            #{m.rank} {m.file.path}
                          </span>
                          <span className="triage-file-score">
                            score: {Math.round(m.score * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer: Labels & Deep-Link Action */}
                <div className="triage-card-footer">
                  <div className="triage-labels">
                    {Array.isArray(issue.labels) &&
                      issue.labels.map((lbl, idx) => (
                        <span key={idx} className="triage-label-pill">
                          {lbl}
                        </span>
                      ))}
                  </div>

                  {onSelectIssueForMapping && (
                    <button
                      type="button"
                      className="triage-map-btn"
                      onClick={() =>
                        onSelectIssueForMapping({
                          number: issue.number,
                          title: issue.title,
                          body: issue.body,
                        })
                      }
                      title="Launch Multi-Signal Bug Localization for this issue"
                    >
                      🎯 Map Responsible Files →
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
