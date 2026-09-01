import React, { useState } from "react";
import type { ArchitectureComponent, ArchitectureRelationship } from "../../api";

interface ComponentDetailDrawerProps {
  component: ArchitectureComponent | null;
  relationships: ArchitectureRelationship[];
  allComponents: ArchitectureComponent[];
  onClose: () => void;
}

type DrawerTab = "overview" | "internal_flow" | "files" | "evidence";

export const ComponentDetailDrawer: React.FC<ComponentDetailDrawerProps> = ({
  component,
  relationships,
  allComponents,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<DrawerTab>("overview");

  if (!component) return null;

  const componentMap = new Map(allComponents.map((c) => [c.id, c]));

  // Find incoming and outgoing connections
  const outgoing = relationships.filter((r) => r.source === component.id);
  const incoming = relationships.filter((r) => r.target === component.id);

  return (
    <aside className="arch-detail-drawer" aria-label="Component details">
      <div className="arch-drawer-header">
        <div>
          <span className="arch-comp-type-badge">
            {component.type.replace(/_/g, " ").toUpperCase()}
          </span>
          <h3 className="arch-drawer-title">{component.name}</h3>
        </div>
        <button
          type="button"
          className="arch-drawer-close-btn"
          onClick={onClose}
          aria-label="Close details"
        >
          ✕
        </button>
      </div>

      {/* Navigation Tabs */}
      <div className="arch-drawer-tabs" role="tablist">
        <button
          type="button"
          className={`arch-drawer-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          className={`arch-drawer-tab ${activeTab === "internal_flow" ? "active" : ""}`}
          onClick={() => setActiveTab("internal_flow")}
        >
          Internal Flow ({component.internal_flow?.length || 0})
        </button>
        <button
          type="button"
          className={`arch-drawer-tab ${activeTab === "files" ? "active" : ""}`}
          onClick={() => setActiveTab("files")}
        >
          Files & Symbols ({component.files?.length || 0})
        </button>
        <button
          type="button"
          className={`arch-drawer-tab ${activeTab === "evidence" ? "active" : ""}`}
          onClick={() => setActiveTab("evidence")}
        >
          Evidence
        </button>
      </div>

      <div className="arch-drawer-content">
        {/* 1. OVERVIEW TAB */}
        {activeTab === "overview" && (
          <>
            <section className="arch-drawer-section">
              <h4 className="arch-drawer-section-title">What it does</h4>
              <p className="arch-drawer-desc">{component.description}</p>
            </section>

            {component.responsibilities && component.responsibilities.length > 0 && (
              <section className="arch-drawer-section">
                <h4 className="arch-drawer-section-title">Key Responsibilities</h4>
                <ul className="arch-drawer-list">
                  {component.responsibilities.map((resp, i) => (
                    <li key={i}>{resp}</li>
                  ))}
                </ul>
              </section>
            )}

            {(outgoing.length > 0 || incoming.length > 0) && (
              <section className="arch-drawer-section">
                <h4 className="arch-drawer-section-title">Connected Subsystems</h4>
                <div className="arch-connections-list">
                  {outgoing.map((rel, i) => {
                    const targetComp = componentMap.get(rel.target);
                    return (
                      <div key={`out-${i}`} className="arch-connection-pill outgoing">
                        <span className="flow-direction">Calls ➔</span>
                        <strong>{targetComp?.name || rel.target}</strong>
                        <span className="flow-label">({rel.label})</span>
                      </div>
                    );
                  })}

                  {incoming.map((rel, i) => {
                    const sourceComp = componentMap.get(rel.source);
                    return (
                      <div key={`in-${i}`} className="arch-connection-pill incoming">
                        <span className="flow-direction">⬅ Called by</span>
                        <strong>{sourceComp?.name || rel.source}</strong>
                        <span className="flow-label">({rel.label})</span>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </>
        )}

        {/* 2. INTERNAL FLOW TAB */}
        {activeTab === "internal_flow" && (
          <section className="arch-drawer-section">
            <h4 className="arch-drawer-section-title">Internal Call Sequence</h4>
            {component.internal_flow && component.internal_flow.length > 0 ? (
              <div className="arch-internal-flow-list">
                {component.internal_flow.map((step, idx) => (
                  <div key={idx} className="arch-internal-flow-step">
                    <div className="step-num">{idx + 1}</div>
                    <div className="step-content">
                      <div className="step-symbols">
                        <code>{step.from_symbol}</code>
                        <span className="step-arrow">➔</span>
                        <code>{step.to_symbol}</code>
                      </div>
                      <p className="step-action">{step.action}</p>
                      {step.file_path && (
                        <div className="step-file">
                          <span>File:</span> <code>{step.file_path}</code>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="arch-drawer-empty">No internal call steps recorded for this subsystem.</p>
            )}
          </section>
        )}

        {/* 3. FILES & SYMBOLS TAB */}
        {activeTab === "files" && (
          <>
            {component.routes && component.routes.length > 0 && (
              <section className="arch-drawer-section">
                <h4 className="arch-drawer-section-title">Handled API Routes</h4>
                <ul className="arch-routes-list">
                  {component.routes.map((route, i) => (
                    <li key={i} className="arch-route-item">
                      <code>{route}</code>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {component.symbols && component.symbols.length > 0 && (
              <section className="arch-drawer-section">
                <h4 className="arch-drawer-section-title">Key Declared Symbols</h4>
                <div className="arch-symbols-cloud">
                  {component.symbols.map((sym, i) => (
                    <span key={i} className="arch-symbol-tag">
                      {sym}
                    </span>
                  ))}
                </div>
              </section>
            )}

            <section className="arch-drawer-section">
              <div className="arch-drawer-section-header">
                <h4 className="arch-drawer-section-title">Implementation Files</h4>
                <span className="arch-badge-count">{component.files?.length || 0} files</span>
              </div>

              {component.files && component.files.length > 0 ? (
                <ul className="arch-files-list">
                  {component.files.map((file, i) => (
                    <li key={i} className="arch-file-item">
                      <code>{file}</code>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="arch-drawer-empty">Logical service / external component.</p>
              )}
            </section>
          </>
        )}

        {/* 4. EVIDENCE TAB */}
        {activeTab === "evidence" && (
          <section className="arch-drawer-section">
            <h4 className="arch-drawer-section-title">Grounding Evidence & Signals</h4>
            {component.evidence?.keywords && component.evidence.keywords.length > 0 && (
              <div style={{ marginBottom: "1rem" }}>
                <p className="eyebrow">Detected Technologies & Patterns</p>
                <div className="arch-keywords-cloud">
                  {component.evidence.keywords.map((kw, i) => (
                    <span key={i} className="arch-keyword-tag">
                      #{kw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {component.evidence?.files && component.evidence.files.length > 0 && (
              <div>
                <p className="eyebrow">Evidence Source Files</p>
                <ul className="arch-files-list">
                  {component.evidence.files.map((f, i) => (
                    <li key={i} className="arch-file-item">
                      <code>{f}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>
    </aside>
  );
};
