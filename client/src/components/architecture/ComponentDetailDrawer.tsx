import React from "react";
import type { ArchitectureComponent, ArchitectureRelationship } from "../../api";

interface ComponentDetailDrawerProps {
  component: ArchitectureComponent | null;
  relationships: ArchitectureRelationship[];
  allComponents: ArchitectureComponent[];
  onClose: () => void;
}

export const ComponentDetailDrawer: React.FC<ComponentDetailDrawerProps> = ({
  component,
  relationships,
  allComponents,
  onClose,
}) => {
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

      <div className="arch-drawer-content">
        {/* Description */}
        <section className="arch-drawer-section">
          <h4 className="arch-drawer-section-title">What it does</h4>
          <p className="arch-drawer-desc">{component.description}</p>
        </section>

        {/* Responsibilities */}
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

        {/* Data Flows & Connections */}
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

        {/* Implementation Files */}
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

        {/* Evidence & Grounding */}
        {component.evidence && (
          <section className="arch-drawer-section">
            <h4 className="arch-drawer-section-title">Evidence & Classification</h4>
            {component.evidence.keywords && component.evidence.keywords.length > 0 && (
              <div className="arch-keywords-cloud">
                {component.evidence.keywords.map((kw, i) => (
                  <span key={i} className="arch-keyword-tag">
                    #{kw}
                  </span>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </aside>
  );
};
