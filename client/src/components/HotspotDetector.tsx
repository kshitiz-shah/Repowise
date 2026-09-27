import { useEffect, useMemo, useState } from "react";
import * as api from "../api";
import type { HotspotAnalysisResponse, HotspotComponentRisk, HotspotFileItem, Repository } from "../api";
import "./HotspotDetector.css";

interface HotspotDetectorProps {
  repository: Repository;
  token: string;
  run: (label: string, action: () => Promise<void>) => Promise<void>;
  loading: string | null;
}

export function HotspotDetector({ repository, token, run, loading }: HotspotDetectorProps) {
  const storageKey = `repowise_hotspots_${repository.id}`;
  const [data, setData] = useState<HotspotAnalysisResponse | null>(() => {
    try {
      const cached = sessionStorage.getItem(storageKey);
      return cached ? (JSON.parse(cached) as HotspotAnalysisResponse) : null;
    } catch {
      return null;
    }
  });
  const [selectedComponent, setSelectedComponent] = useState<string>("ALL");
  const [selectedRisk, setSelectedRisk] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [highlightedFile, setHighlightedFile] = useState<HotspotFileItem | null>(null);

  useEffect(() => {
    let isMounted = true;
    void api.getHotspots(token, repository.id)
      .then((res) => {
        if (!isMounted) return;
        setData(res);
        try {
          sessionStorage.setItem(storageKey, JSON.stringify(res));
        } catch {}
      })
      .catch((err) => {
        console.warn("Could not load hotspots:", err);
      });

    return () => {
      isMounted = false;
    };
  }, [repository.id, token, storageKey]);

  const handleRecalculate = async () => {
    await run("calc-hotspots", async () => {
      const res = await api.calculateHotspots(token, repository.id);
      setData(res);
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(res));
      } catch {}
    });
  };

  const filteredFiles = useMemo(() => {
    if (!data?.files) return [];
    return data.files.filter((f) => {
      // Component filter
      if (selectedComponent !== "ALL" && f.componentName !== selectedComponent) {
        return false;
      }

      // Risk level filter
      if (selectedRisk !== "ALL" && f.risk_level !== selectedRisk) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesPath = f.path.toLowerCase().includes(q);
        const matchesDrivers = f.evidence?.drivers.some((d) => d.toLowerCase().includes(q));
        if (!matchesPath && !matchesDrivers) return false;
      }

      return true;
    });
  }, [data?.files, selectedComponent, selectedRisk, searchQuery]);

  const components = data?.components || [];
  const maxBugsAcrossAll = useMemo(() => {
    if (!data?.files || data.files.length === 0) return 1;
    return Math.max(...data.files.map((f) => f.bugCount), 1);
  }, [data?.files]);

  return (
    <div className="hotspots-container">
      {/* Overview Stat Cards */}
      <div className="hotspots-stats">
        <div className="hotspot-stat-card critical">
          <span className="hotspot-stat-lbl">Critical Risk Files</span>
          <span className="hotspot-stat-val">
            {data?.files.filter((f) => f.risk_level === "CRITICAL").length ?? 0}
          </span>
        </div>
        <div className="hotspot-stat-card high">
          <span className="hotspot-stat-lbl">High Risk Files</span>
          <span className="hotspot-stat-val">
            {data?.files.filter((f) => f.risk_level === "HIGH").length ?? 0}
          </span>
        </div>
        <div className="hotspot-stat-card medium">
          <span className="hotspot-stat-lbl">Medium Risk Files</span>
          <span className="hotspot-stat-val">
            {data?.files.filter((f) => f.risk_level === "MEDIUM").length ?? 0}
          </span>
        </div>
        <div className="hotspot-stat-card low">
          <span className="hotspot-stat-lbl">Stable Files</span>
          <span className="hotspot-stat-val">
            {data?.files.filter((f) => f.risk_level === "LOW").length ?? 0}
          </span>
        </div>
      </div>

      {/* Component Risk Heatmap */}
      {components.length > 0 && (
        <div>
          <div className="hotspot-section-title">
            <span>Architectural Component Risk Heatmap</span>
            {selectedComponent !== "ALL" && (
              <button
                type="button"
                className="triage-pill"
                onClick={() => setSelectedComponent("ALL")}
                style={{ fontSize: "0.75rem" }}
              >
                Clear Filter ({selectedComponent}) ✕
              </button>
            )}
          </div>
          <div className="component-heatmap-grid">
            {components.map((c) => {
              const cardClass = `card-${c.risk_level.toLowerCase()}`;
              const isSelected = selectedComponent === c.name;
              return (
                <div
                  key={c.name}
                  className={`component-risk-card ${cardClass} ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedComponent(isSelected ? "ALL" : c.name)}
                  title={`Filter files in ${c.name}`}
                >
                  <div className="comp-header">
                    <span className="comp-name">{c.name}</span>
                    <span className={`severity-badge severity-${c.risk_level.toLowerCase()}`}>
                      {c.risk_level}
                    </span>
                  </div>
                  <div className="comp-metrics">
                    <span>
                      Avg Risk: <strong>{Math.round(c.avg_risk_score * 100)}%</strong>
                    </span>
                    <span>
                      Files: <strong>{c.file_count}</strong>
                    </span>
                    <span>
                      Total Churn: <strong>{c.total_churn}</strong>
                    </span>
                    <span>
                      Bug Density: <strong>{c.total_bug_density}</strong>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 2D Risk Scatter Matrix: Churn vs Bug Density */}
      {data?.files && data.files.length > 0 && (
        <div className="hotspot-matrix-card">
          <div className="hotspot-section-title" style={{ margin: 0 }}>
            <span>Interactive Risk Matrix (Commit Churn vs. Bug Density)</span>
            <span style={{ fontSize: "0.78rem", color: "var(--text-muted, #64748b)" }}>
              Top-Right quadrant represents critical maintenance hotspots
            </span>
          </div>

          <div style={{ position: "relative" }}>
            <span className="matrix-axis-label-y" style={{ position: "absolute", top: 0, left: 8 }}>
              ▲ High Bug Density
            </span>
            <div className="hotspot-matrix-chart">
              {data.files.map((file) => {
                // X: Churn Score (0 to 1) -> 5% to 95%
                const xPercent = 5 + (file.churnScore || 0) * 88;
                // Y: Bug Count / maxBugs -> 5% to 90% from bottom
                const yPercent = 5 + (file.bugCount / maxBugsAcrossAll) * 85;
                const dotClass = `dot-${file.risk_level.toLowerCase()}`;
                const isHighlighted = highlightedFile?.id === file.id;

                return (
                  <div
                    key={file.id}
                    className={`matrix-dot ${dotClass}`}
                    style={{
                      left: `${xPercent}%`,
                      bottom: `${yPercent}%`,
                      transform: isHighlighted
                        ? "translate(-50%, 50%) scale(2.2)"
                        : undefined,
                      zIndex: isHighlighted ? 20 : undefined,
                    }}
                    onClick={() => {
                      setHighlightedFile(file);
                      setSearchQuery(file.name);
                    }}
                    title={`${file.path}\nRisk: ${Math.round((file.riskScore || 0) * 100)}% (${file.risk_level})\nChurn: ${Math.round((file.churnScore || 0) * 100)}%\nBugs: ${file.bugCount}`}
                  />
                );
              })}
            </div>
            <div className="matrix-axis-label-x">
              Commit Churn Frequency (Low → High) ▶
            </div>
          </div>
        </div>
      )}

      {/* Toolbar: Search, Filters & Actions */}
      <div className="hotspot-toolbar">
        <div className="triage-search-box">
          <input
            type="text"
            className="triage-search-input"
            placeholder="Search files by path or risk drivers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="triage-filters">
          <button
            type="button"
            className={`triage-pill ${selectedRisk === "ALL" ? "active" : ""}`}
            onClick={() => setSelectedRisk("ALL")}
          >
            All Risk Levels
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedRisk === "CRITICAL" ? "active" : ""}`}
            onClick={() => setSelectedRisk("CRITICAL")}
          >
            Critical
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedRisk === "HIGH" ? "active" : ""}`}
            onClick={() => setSelectedRisk("HIGH")}
          >
            High
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedRisk === "MEDIUM" ? "active" : ""}`}
            onClick={() => setSelectedRisk("MEDIUM")}
          >
            Medium
          </button>
          <button
            type="button"
            className={`triage-pill ${selectedRisk === "LOW" ? "active" : ""}`}
            onClick={() => setSelectedRisk("LOW")}
          >
            Low
          </button>
        </div>

        <button
          type="button"
          className="triage-btn triage-btn-primary"
          onClick={handleRecalculate}
          disabled={loading !== null}
        >
          {loading === "calc-hotspots" ? "Calculating Risk Scores…" : "⚡ Recalculate Risk Telemetry"}
        </button>
      </div>

      {/* Ranked Hotspot Files List */}
      {filteredFiles.length === 0 ? (
        <div className="triage-empty-state">
          <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🔥</div>
          <h4>No hotspot files found</h4>
          <p>
            {data?.files && data.files.length > 0
              ? "No files match the currently selected filter."
              : "Click “Recalculate Risk Telemetry” to analyze git commits, bug mappings, and dependency architecture."}
          </p>
        </div>
      ) : (
        <div className="hotspot-file-list">
          {filteredFiles.map((file) => {
            const riskPct = Math.round((file.riskScore || 0) * 100);
            const levelClass = file.risk_level.toLowerCase();
            const borderClass = `border-${levelClass}`;
            const fillClass = `fill-${levelClass}`;
            const scoreBadgeClass = `score-${levelClass}`;

            return (
              <div key={file.id} className={`hotspot-file-card ${borderClass}`}>
                <div className="hotspot-file-header">
                  <div>
                    <span className="hotspot-file-path">{file.path}</span>
                    <div className="hotspot-file-meta">
                      {file.componentName && <span>📁 {file.componentName}</span>}
                      {file.language && <span>⚙️ {file.language}</span>}
                      {file.linesOfCode ? <span>📏 {file.linesOfCode} LOC</span> : null}
                    </div>
                  </div>

                  <span className={`hotspot-risk-score-badge ${scoreBadgeClass}`}>
                    {riskPct}% — {file.risk_level}
                  </span>
                </div>

                {/* Risk score bar */}
                <div className="hotspot-meter-bar-track">
                  <div
                    className={`hotspot-meter-bar-fill ${fillClass}`}
                    style={{ width: `${Math.max(riskPct, 6)}%` }}
                  />
                </div>

                {/* Signals breakdown */}
                <div className="hotspot-signals-grid">
                  <div className="hotspot-signal-item">
                    <span>Commit Churn</span>
                    <span>{file.evidence?.churn_commits ?? 0} commits ({Math.round((file.churnScore || 0) * 100)}%)</span>
                  </div>
                  <div className="hotspot-signal-item">
                    <span>Bug Associations</span>
                    <span>{file.bugCount} bugs</span>
                  </div>
                  <div className="hotspot-signal-item">
                    <span>Bug-Fix Commits</span>
                    <span>{file.evidence?.bug_fix_commits ?? 0} patches</span>
                  </div>
                  <div className="hotspot-signal-item">
                    <span>In-Degree Centrality</span>
                    <span>{file.evidence?.in_degree ?? 0} callers</span>
                  </div>
                </div>

                {/* Explainable Risk Drivers */}
                {file.evidence?.drivers && file.evidence.drivers.length > 0 && (
                  <div className="hotspot-drivers-box">
                    {file.evidence.drivers.map((driver, dIdx) => (
                      <span key={dIdx} className="hotspot-driver-tag">
                        {driver}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
