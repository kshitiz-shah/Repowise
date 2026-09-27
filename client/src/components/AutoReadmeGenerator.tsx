import { useEffect, useState } from "react";
import * as api from "../api";
import type { AutoReadmeResult, Repository } from "../api";
import { FormattedAnswer } from "./FormattedAnswer";
import "./AutoReadmeGenerator.css";

interface AutoReadmeGeneratorProps {
  repository: Repository;
  token: string;
  run: (label: string, action: () => Promise<void>) => Promise<void>;
  loading: string | null;
}

export function AutoReadmeGenerator({ repository, token, run, loading }: AutoReadmeGeneratorProps) {
  const storageKey = `repowise_readme_${repository.id}`;

  const [readme, setReadme] = useState<AutoReadmeResult | null>(() => {
    try {
      const cached = sessionStorage.getItem(storageKey);
      return cached ? (JSON.parse(cached) as AutoReadmeResult) : null;
    } catch {
      return null;
    }
  });
  const [existingReadme, setExistingReadme] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState<"preview" | "raw" | "diff">("preview");
  const [copied, setCopied] = useState<boolean>(false);
  const [editedMarkdown, setEditedMarkdown] = useState<string>(() => {
    try {
      const cached = sessionStorage.getItem(storageKey);
      if (cached) {
        const parsed = JSON.parse(cached);
        return parsed.markdown || "";
      }
    } catch {}
    return "";
  });

  useEffect(() => {
    let isMounted = true;
    void api.getReadme(token, repository.id)
      .then((res) => {
        if (!isMounted) return;
        if ("markdown" in res) {
          setReadme((prev) => prev ?? (res as AutoReadmeResult));
          setEditedMarkdown((prev) => prev || (res.markdown as string));
          try {
            sessionStorage.setItem(storageKey, JSON.stringify(res));
          } catch {}
          setExistingReadme(res.existing_readme ?? null);
        } else if ("existing_readme" in res) {
          setExistingReadme(res.existing_readme ?? null);
        }
      })
      .catch((err) => {
        console.warn("Could not load existing README:", err);
      });

    return () => {
      isMounted = false;
    };
  }, [repository.id, token, storageKey]);

  const handleGenerate = async () => {
    await run("generate-readme", async () => {
      const res = await api.generateReadme(token, repository.id);
      setReadme(res);
      setEditedMarkdown(res.markdown);
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(res));
      } catch {}
      if (res.existing_readme) {
        setExistingReadme(res.existing_readme);
      }
    });
  };

  const handleCopy = () => {
    const textToCopy = editedMarkdown || readme?.markdown || "";
    if (!textToCopy) return;
    void navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const textToDownload = editedMarkdown || readme?.markdown || "";
    if (!textToDownload) return;
    const blob = new Blob([textToDownload], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "README.md");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const currentMarkdown = editedMarkdown || readme?.markdown || "";

  return (
    <div className="readme-container">
      {/* Evidence Panel (if generated) */}
      {readme && (
        <div className="readme-evidence-card">
          <div className="hotspot-section-title" style={{ margin: 0 }}>
            <span>Verified Code Evidence (Anti-Hallucination Grounding)</span>
            <span style={{ fontSize: "0.76rem", color: "var(--text-muted, #64748b)" }}>
              Strictly matched against actual build configs and source files
            </span>
          </div>

          <div className="readme-evidence-grid">
            {/* Tech Stack */}
            {readme.tech_stack && readme.tech_stack.length > 0 && (
              <div className="readme-evidence-block">
                <span className="readme-evidence-title">Detected Technologies</span>
                <div className="readme-tag-list">
                  {readme.tech_stack.map((t, idx) => (
                    <span key={idx} className="readme-tag tag-tech">
                      {t.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Verified Scripts */}
            {readme.quick_start?.run_commands && readme.quick_start.run_commands.length > 0 && (
              <div className="readme-evidence-block">
                <span className="readme-evidence-title">Verified Run Commands</span>
                <div className="readme-tag-list">
                  {readme.quick_start.run_commands.map((c, idx) => (
                    <span key={idx} className="readme-tag tag-script" title={c.label}>
                      {c.command}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Verified Env Vars */}
            {readme.quick_start?.environment_variables && readme.quick_start.environment_variables.length > 0 && (
              <div className="readme-evidence-block">
                <span className="readme-evidence-title">Verified Environment Variables</span>
                <div className="readme-tag-list">
                  {readme.quick_start.environment_variables.map((ev, idx) => (
                    <span key={idx} className="readme-tag tag-env" title={ev.description}>
                      {ev.key}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="readme-toolbar">
        <div className="readme-view-toggles">
          <button
            type="button"
            className={`triage-pill ${activeMode === "preview" ? "active" : ""}`}
            onClick={() => setActiveMode("preview")}
          >
            👁️ Formatted Preview
          </button>
          <button
            type="button"
            className={`triage-pill ${activeMode === "raw" ? "active" : ""}`}
            onClick={() => setActiveMode("raw")}
          >
            📝 Raw Markdown
          </button>
          {existingReadme && (
            <button
              type="button"
              className={`triage-pill ${activeMode === "diff" ? "active" : ""}`}
              onClick={() => setActiveMode("diff")}
            >
              🔄 Diff vs Existing
            </button>
          )}
        </div>

        <div className="readme-action-buttons">
          <button
            type="button"
            className="triage-btn triage-btn-secondary"
            onClick={handleCopy}
            disabled={!currentMarkdown}
          >
            {copied ? "✓ Copied to Clipboard!" : "📋 Copy Markdown"}
          </button>
          <button
            type="button"
            className="triage-btn triage-btn-secondary"
            onClick={handleDownload}
            disabled={!currentMarkdown}
          >
            ⬇️ Download README.md
          </button>
          <button
            type="button"
            className="triage-btn triage-btn-primary"
            onClick={handleGenerate}
            disabled={loading !== null}
          >
            {loading === "generate-readme" ? "Analyzing Code Evidence…" : "⚡ Generate Grounded README"}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {!currentMarkdown ? (
        <div className="triage-empty-state">
          <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>📝</div>
          <h4>No generated README yet</h4>
          <p>
            Generate a code-grounded, production-ready README based on real scripts, environment variables,
            and entry points discovered in the repository.
          </p>
          <button
            type="button"
            className="triage-btn triage-btn-primary"
            onClick={handleGenerate}
            disabled={loading !== null}
          >
            ⚡ Generate Grounded README Now
          </button>
        </div>
      ) : (
        <div className="readme-display-box">
          <div className="readme-display-header">
            <span>
              {activeMode === "preview" && "Rendered GitHub-Flavored Markdown Preview"}
              {activeMode === "raw" && "Editable Markdown Source"}
              {activeMode === "diff" && "Side-by-Side Comparison (Existing vs. Grounded)"}
            </span>
            <span style={{ fontSize: "0.78rem" }}>
              {currentMarkdown.split("\n").length} lines · {currentMarkdown.length} characters
            </span>
          </div>

          {activeMode === "preview" && (
            <div className="readme-preview-content">
              <FormattedAnswer content={currentMarkdown} />
            </div>
          )}

          {activeMode === "raw" && (
            <textarea
              className="readme-raw-editor"
              value={editedMarkdown}
              onChange={(e) => setEditedMarkdown(e.target.value)}
              placeholder="README Markdown content..."
            />
          )}

          {activeMode === "diff" && existingReadme && (
            <div className="readme-diff-container">
              <div className="readme-diff-pane">
                <div className="readme-diff-pane-title">
                  Existing Repository README (from GitHub)
                </div>
                <div className="readme-diff-body old-body">
                  {existingReadme}
                </div>
              </div>
              <div className="readme-diff-pane">
                <div className="readme-diff-pane-title">
                  New Code-Grounded README (RepoWise)
                </div>
                <div className="readme-diff-body new-body">
                  {currentMarkdown}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
