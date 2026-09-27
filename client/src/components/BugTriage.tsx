import { FormEvent, useEffect, useState } from "react";
import * as api from "../api";
import type { BugLocalizationResult, FileCandidate, Repository } from "../api";
import "./BugTriage.css";

interface BugTriageProps {
  repository: Repository;
  token: string;
  run: (label: string, action: () => Promise<void>) => Promise<void>;
  loading: string | null;
}

interface BugPreset {
  name: string;
  number: number;
  title: string;
  body: string;
}

const PRESETS: BugPreset[] = [
  {
    name: "Authentication / JWT Expiry",
    number: 42,
    title: "Token refresh fails intermittently during session renewal",
    body: "Users are encountering InvalidTokenError: jwt expired when calling the refresh token route. This results in unintended logouts during active sessions.",
  },
  {
    name: "Database Connection Pool",
    number: 18,
    title: "PrismaClientInitializationError: Connection pool exhausted under concurrent load",
    body: "Database operations in repository queries timeout with P2024 connection pool timeout under concurrent requests.",
  },
  {
    name: "Architecture Rendering Exception",
    number: 104,
    title: "TypeError: Cannot read properties of undefined (reading 'nodes')",
    body: "Opening architecture diagrams for repositories containing empty directories throws an unhandled exception when computing layout dimensions.",
  },
];

export function BugTriage({ repository, token, run, loading }: BugTriageProps) {
  const [issueNumber, setIssueNumber] = useState<number>(42);
  const [issueTitle, setIssueTitle] = useState<string>(PRESETS[0].title);
  const [issueBody, setIssueBody] = useState<string>(PRESETS[0].body);
  const [topK, setTopK] = useState<number>(5);
  const [includeExplanation, setIncludeExplanation] = useState<boolean>(true);
  const [fetchingIssue, setFetchingIssue] = useState<boolean>(false);
  const [result, setResult] = useState<BugLocalizationResult | null>(null);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(0);
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Load history on repository change
  useEffect(() => {
    setResult(null);
    setStatusMessage(null);
    api
      .getBugMappingsHistory(token, repository.id)
      .then((data) => setHistory(data as any[]))
      .catch(() => setHistory([]));
  }, [repository.id, token]);

  const handleApplyPreset = (preset: BugPreset) => {
    setIssueNumber(preset.number);
    setIssueTitle(preset.title);
    setIssueBody(preset.body);
    setStatusMessage(`Loaded preset: "${preset.name}"`);
  };

  const handleFetchGitHubIssue = async () => {
    if (!issueNumber || issueNumber <= 0) return;
    setFetchingIssue(true);
    setStatusMessage(null);
    try {
      const issue = await api.fetchGitHubIssue(token, repository.id, issueNumber);
      setIssueTitle(issue.title);
      setIssueBody(issue.body ?? "");
      setStatusMessage(`Successfully fetched Issue #${issue.number} from GitHub.`);
    } catch (err) {
      setStatusMessage(
        err instanceof Error
          ? err.message
          : `Could not fetch Issue #${issueNumber} from GitHub. (You can still enter it manually).`
      );
    } finally {
      setFetchingIssue(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!issueTitle.trim()) return;

    void run("bug-localize", async () => {
      setStatusMessage(null);
      const res = await api.localizeBug(token, repository.id, {
        number: issueNumber,
        title: issueTitle.trim(),
        body: issueBody.trim(),
        topK,
        includeExplanation,
      });
      setResult(res);
      setExpandedIndex(0); // expand top candidate
      // Refresh history
      api
        .getBugMappingsHistory(token, repository.id)
        .then((data) => setHistory(data as any[]))
        .catch(() => {});
    });
  };

  const isLocalizing = loading === "bug-localize";

  return (
    <div className="bug-triage-container">
      {/* Preset Quick Buttons */}
      <div className="bug-presets">
        <span className="bug-presets-label">⚡ Sample Bug Scenarios:</span>
        {PRESETS.map((preset) => (
          <button
            key={preset.name}
            type="button"
            className="bug-preset-pill"
            onClick={() => handleApplyPreset(preset)}
          >
            {preset.name}
          </button>
        ))}
        {history.length > 0 && (
          <button
            type="button"
            className="bug-preset-pill"
            style={{ marginLeft: "auto", fontWeight: 700 }}
            onClick={() => setShowHistory(!showHistory)}
          >
            {showHistory ? "✕ Hide History" : `📜 History (${history.length})`}
          </button>
        )}
      </div>

      {/* History Drawer */}
      {showHistory && history.length > 0 && (
        <div className="bug-history-list">
          <p className="eyebrow">Past Triaged Issues in this Repository</p>
          {history.map((item) => (
            <div
              key={item.id}
              className="bug-history-item"
              onClick={() => {
                setIssueNumber(item.number);
                setIssueTitle(item.title);
                setIssueBody(item.body ?? "");
                setShowHistory(false);
              }}
            >
              <div>
                <strong>
                  #{item.number} {item.title}
                </strong>
                <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--ink-muted)" }}>
                  {item.fileMappings?.length ?? 0} mapped files · {new Date(item.createdAt).toLocaleDateString()}
                </p>
              </div>
              <span className="bug-preset-pill">Load →</span>
            </div>
          ))}
        </div>
      )}

      {/* Input Form Card */}
      <form className="bug-form-card" onSubmit={handleSubmit}>
        <div className="bug-form-row">
          <div className="bug-field small">
            <label htmlFor="issue-number">Issue #</label>
            <input
              id="issue-number"
              type="number"
              min={1}
              value={issueNumber}
              onChange={(e) => setIssueNumber(parseInt(e.target.value, 10) || 1)}
              required
            />
          </div>

          <button
            type="button"
            className="bug-fetch-btn"
            onClick={handleFetchGitHubIssue}
            disabled={fetchingIssue || isLocalizing}
            title="Fetch issue details directly from GitHub API"
          >
            {fetchingIssue ? "Fetching…" : "Fetch from GitHub ↗"}
          </button>

          <div className="bug-field">
            <label htmlFor="issue-title">Issue Title / Bug Summary</label>
            <input
              id="issue-title"
              type="text"
              required
              minLength={3}
              value={issueTitle}
              onChange={(e) => setIssueTitle(e.target.value)}
              placeholder="e.g. InvalidTokenError on token refresh"
            />
          </div>
        </div>

        <div className="bug-field">
          <label htmlFor="issue-body">Issue Description / Stack Trace / Error Details (Optional)</label>
          <textarea
            id="issue-body"
            rows={3}
            value={issueBody}
            onChange={(e) => setIssueBody(e.target.value)}
            placeholder="Paste error logs, stack traces, expected vs actual behavior, or reproduction steps..."
          />
        </div>

        <div className="bug-actions-bar">
          <div className="bug-options">
            <label>
              Candidates:
              <select
                value={topK}
                onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                disabled={isLocalizing}
              >
                <option value={3}>Top 3</option>
                <option value={5}>Top 5</option>
                <option value={8}>Top 8</option>
              </select>
            </label>
            <label>
              <input
                type="checkbox"
                checked={includeExplanation}
                onChange={(e) => setIncludeExplanation(e.target.checked)}
                disabled={isLocalizing}
              />
              Grounded AI Explanations
            </label>
          </div>

          <button type="submit" className="bug-submit-btn" disabled={isLocalizing}>
            {isLocalizing ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Analyzing multi-signal pipeline…
              </>
            ) : (
              <>🎯 Locate Responsible Files</>
            )}
          </button>
        </div>
      </form>

      {statusMessage && (
        <p className="notice" role="status" style={{ margin: 0 }}>
          {statusMessage}
        </p>
      )}

      {/* Results View */}
      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* Executive Summary Card */}
          <div className="bug-summary-card">
            <div className="bug-summary-header">
              <div>
                <p className="eyebrow" style={{ margin: 0 }}>
                  Multi-Signal Triage Assessment
                </p>
                <h4 style={{ margin: "0.25rem 0 0", fontSize: "1.1rem" }}>
                  Issue #{issueNumber}: {result.issue_analysis.problem_summary}
                </h4>
              </div>
              <span className="bug-subsystem-badge">
                Layer: {result.issue_analysis.affected_subsystem}
              </span>
            </div>

            <p className="bug-summary-text">{result.analysis_summary}</p>

            <div className="bug-extracted-signals">
              {result.issue_analysis.domain_concepts.map((concept) => (
                <span key={concept} className="bug-tag">
                  💡 {concept}
                </span>
              ))}
              {result.issue_analysis.entities.map((entity) => (
                <span key={entity} className="bug-tag entity">
                  ⚙️ {entity}
                </span>
              ))}
              {result.issue_analysis.error_messages.map((err) => (
                <span key={err} className="bug-tag error">
                  ⚠️ {err}
                </span>
              ))}
              {result.issue_analysis.file_path_hints.map((hint) => (
                <span key={hint} className="bug-tag">
                  📁 {hint}
                </span>
              ))}
            </div>
          </div>

          {/* Ranked Candidates Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <p className="eyebrow" style={{ margin: 0 }}>
                Ranked File Candidates
              </p>
              <h3 style={{ margin: "0.2rem 0 0" }}>
                Identified {result.candidates.length} Most Likely Source Files
              </h3>
            </div>
            <span className="badge">
              Scored across {result.total_files_analyzed} repository files
            </span>
          </div>

          {/* Candidates List */}
          <div className="bug-candidates-list">
            {result.candidates.map((candidate, idx) => (
              <CandidateCard
                key={candidate.file_path}
                candidate={candidate}
                isExpanded={expandedIndex === idx}
                onToggle={() => setExpandedIndex(expandedIndex === idx ? null : idx)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CandidateCard({
  candidate,
  isExpanded,
  onToggle,
}: {
  candidate: FileCandidate;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const rankClass =
    candidate.rank === 1 ? "rank-1" : candidate.rank === 2 ? "rank-2" : candidate.rank === 3 ? "rank-3" : "";

  return (
    <div className={`bug-candidate-card ${rankClass}`}>
      {/* Top Header: Rank, File Path, Overall Score */}
      <div className="bug-candidate-top">
        <div className="bug-candidate-meta">
          <div className="bug-rank-badge">#{candidate.rank}</div>
          <div>
            <div className="bug-candidate-path">{candidate.file_path}</div>
            <span style={{ fontSize: "0.78rem", color: "var(--ink-muted)" }}>
              Confidence: {Math.round(candidate.confidence * 100)}%
            </span>
          </div>
        </div>

        <div className="bug-score-badge">
          <div className="bug-score-number">{Math.round(candidate.final_score * 100)}%</div>
          <div className="bug-score-label">Match Probability</div>
        </div>
      </div>

      {/* The 5 Explainable Signals Breakdown */}
      <div className="bug-signals-grid">
        <SignalItem
          label="Semantic Similarity"
          weight="35%"
          score={candidate.signals.semantic_similarity}
          className="semantic"
          icon="🧠"
        />
        <SignalItem
          label="Keyword & Symbols"
          weight="25%"
          score={candidate.signals.keyword_score}
          className="keyword"
          icon="🏷️"
        />
        <SignalItem
          label="Dependency Link"
          weight="15%"
          score={candidate.signals.dependency_score}
          className="dependency"
          icon="🕸️"
        />
        <SignalItem
          label="Path & Module"
          weight="10%"
          score={candidate.signals.path_score}
          className="path"
          icon="📁"
        />
        <SignalItem
          label="Git Churn & Fixes"
          weight="15%"
          score={candidate.signals.historical_score}
          className="historical"
          icon="📜"
        />
      </div>

      {/* Grounded AI Explanation Box */}
      {candidate.explanation && (
        <div className="bug-explanation-box">
          <div className="bug-explanation-label">🔍 Why this file was selected</div>
          <div>{candidate.explanation}</div>
        </div>
      )}

      {/* Expandable Evidence Drawer */}
      <div className="bug-evidence-section">
        <button type="button" className="bug-evidence-toggle" onClick={onToggle}>
          <span>{isExpanded ? "▾ Hide Evidence & Code Details" : "▸ View Evidence & Code Snippets"}</span>
          <span style={{ fontSize: "0.75rem", opacity: 0.8 }}>
            ({candidate.evidence.matched_symbols.length} symbols, {candidate.evidence.matched_keywords.length} keywords,{" "}
            {candidate.evidence.relevant_chunks.length} chunks)
          </span>
        </button>

        {isExpanded && (
          <div className="bug-evidence-details">
            {candidate.evidence.matched_symbols.length > 0 && (
              <div className="bug-evidence-row">
                <span className="bug-evidence-label">Matched Symbols:</span>
                <div className="bug-evidence-pills">
                  {candidate.evidence.matched_symbols.map((sym) => (
                    <span key={sym} className="bug-pill-item" style={{ color: "var(--terracotta)" }}>
                      fn {sym}()
                    </span>
                  ))}
                </div>
              </div>
            )}

            {candidate.evidence.matched_keywords.length > 0 && (
              <div className="bug-evidence-row">
                <span className="bug-evidence-label">Matched Keywords:</span>
                <div className="bug-evidence-pills">
                  {candidate.evidence.matched_keywords.map((kw) => (
                    <span key={kw} className="bug-pill-item">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {candidate.evidence.dependency_chain.length > 0 && (
              <div className="bug-evidence-row">
                <span className="bug-evidence-label">Dependency Chain:</span>
                <div className="bug-evidence-pills">
                  {candidate.evidence.dependency_chain.map((chain) => (
                    <span key={chain} className="bug-pill-item" style={{ background: "rgba(139, 92, 246, 0.1)" }}>
                      {chain}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {candidate.evidence.relevant_chunks.length > 0 && (
              <div style={{ marginTop: "0.35rem" }}>
                <span className="bug-evidence-label">Relevant Code Ranges:</span>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", marginTop: "0.25rem" }}>
                  {candidate.evidence.relevant_chunks.map((chunk, cIdx) => (
                    <div
                      key={cIdx}
                      style={{
                        padding: "0.4rem 0.6rem",
                        background: "var(--surface-card)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "4px",
                        fontFamily: "JetBrains Mono, monospace",
                        fontSize: "0.78rem",
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span>
                        Lines {chunk.start_line}–{chunk.end_line}
                        {chunk.symbol && ` | ${chunk.symbol}`} ({chunk.chunk_type})
                      </span>
                      <span style={{ color: "var(--terracotta)", fontWeight: 600 }}>
                        {Math.round(chunk.score * 100)}% match
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SignalItem({
  label,
  weight,
  score,
  className,
  icon,
}: {
  label: string;
  weight: string;
  score: number;
  className: string;
  icon: string;
}) {
  const percent = Math.round(score * 100);

  return (
    <div className="bug-signal-item">
      <div className="bug-signal-header">
        <span className="bug-signal-icon-label">
          <span>{icon}</span>
          <span>{label}</span>
        </span>
        <span>
          <strong>{percent}%</strong> <span style={{ opacity: 0.6 }}>({weight})</span>
        </span>
      </div>
      <div className="bug-signal-bar-track">
        <div className={`bug-signal-bar-fill ${className}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
