import React, { useState, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { Architecture, ExecutionFlow } from "./api";
import { useArchitectureGraph } from "./hooks/useArchitectureGraph";
import { useSemanticArchitecture } from "./hooks/useSemanticArchitecture";
import { FolderNode } from "./components/architecture/FolderNode";
import { FileNode } from "./components/architecture/FileNode";
import { ComponentNode } from "./components/architecture/ComponentNode";
import { ContainsEdge } from "./components/architecture/ContainsEdge";
import { ImportEdge } from "./components/architecture/ImportEdge";
import { SemanticEdge } from "./components/architecture/SemanticEdge";
import { ComponentDetailDrawer } from "./components/architecture/ComponentDetailDrawer";
import { MermaidDiagram } from "./components/architecture/MermaidDiagram";
import { compileClientMermaidArchitecture } from "./services/mermaidCompiler";

// Custom Node and Edge Types Map
const fileNodeTypes = {
  archFolder: FolderNode,
  archFile: FileNode,
};

const fileEdgeTypes = {
  archContains: ContainsEdge,
  archImport: ImportEdge,
};

const semanticNodeTypes = {
  semanticComponent: ComponentNode,
};

const semanticEdgeTypes = {
  semanticRelationship: SemanticEdge,
};

interface ArchitectureGraphProps {
  graph: Architecture;
}

type ExplorerTab = "system" | "flows" | "dependencies";
type SystemLayoutMode = "gitdiagram" | "nodes";

export default function ArchitectureGraph({ graph }: ArchitectureGraphProps) {
  const [activeTab, setActiveTab] = useState<ExplorerTab>("system");
  const [systemLayoutMode, setSystemLayoutMode] = useState<SystemLayoutMode>("gitdiagram");
  const [selectedFlowIndex, setSelectedFlowIndex] = useState<number>(0);

  // Hook 1: Semantic System Architecture (High-level Subsystems)
  const {
    flowNodes: semanticNodes,
    flowEdges: semanticEdges,
    selectedComponent,
    selectedComponentId,
    selectComponent,
    clearSelection: clearSemanticSelection,
  } = useSemanticArchitecture(graph.architecture);

  // Hook 2: Hierarchical File Dependencies (Code Details)
  const {
    flowNodes: fileNodes,
    flowEdges: fileEdges,
    selectedFileId,
    clearSelection: clearFileSelection,
  } = useArchitectureGraph(graph);

  const hasSemanticArchitecture = Boolean(
    graph.architecture &&
    graph.architecture.components &&
    graph.architecture.components.length > 0
  );

  const compiledMermaidChart = useMemo(() => {
    if (!graph.architecture) return "";
    if (graph.architecture.mermaid_code && graph.architecture.mermaid_code.trim()) {
      return graph.architecture.mermaid_code;
    }
    return compileClientMermaidArchitecture(graph.architecture);
  }, [graph.architecture]);

  const flows: ExecutionFlow[] = graph.architecture?.flows || [];
  const statistics = graph.statistics;


  return (
    <div className="arch-explorer-container">
      {/* SVG Global Arrow Markers */}
      <svg
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: 0,
          height: 0,
          pointerEvents: "none",
        }}
      >
        <defs>
          {/* Semantic Architecture Arrow */}
          <marker
            id="arch-semantic-arrow"
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path
              d="M1,1 L1,7 L8,4 z"
              fill="#C56A3C"
              stroke="#C56A3C"
              strokeWidth="1"
            />
          </marker>

          {/* File Dependency Graph Arrows */}
          <marker
            id="arch-arrow-default"
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path
              d="M1,1 L1,7 L8,4 z"
              fill="#475069"
              stroke="#475069"
              strokeWidth="1"
            />
          </marker>
          <marker
            id="arch-arrow-highlight"
            markerWidth="12"
            markerHeight="12"
            refX="9"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path
              d="M1,1 L1,7 L9,4 z"
              fill="#C56A3C"
              stroke="#C56A3C"
              strokeWidth="1"
            />
          </marker>
          <marker
            id="arch-arrow-dim"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M1,1 L1,5 L6,3 z" fill="#D8CEBE" opacity="0.5" />
          </marker>
        </defs>
      </svg>

      {/* Top Header & View Tabs */}
      <div className="arch-mode-header">
        <div className="arch-tab-group" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "system"}
            className={`arch-tab-btn ${activeTab === "system" ? "active" : ""}`}
            onClick={() => setActiveTab("system")}
          >
            🏛️ Subsystem Architecture
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "flows"}
            className={`arch-tab-btn ${activeTab === "flows" ? "active" : ""}`}
            onClick={() => setActiveTab("flows")}
          >
            ⚡ Execution Flows ({flows.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "dependencies"}
            className={`arch-tab-btn ${activeTab === "dependencies" ? "active" : ""}`}
            onClick={() => setActiveTab("dependencies")}
          >
            🔗 Code Dependencies
          </button>
        </div>

        {activeTab === "dependencies" && statistics && (
          <div className="arch-stats-group">
            <span className="arch-stat-pill">
              <strong>{statistics.folders}</strong> folders
            </span>
            <span className="arch-stat-pill">
              <strong>{statistics.files}</strong> files
            </span>
            <span className="arch-stat-pill">
              <strong>{statistics.dependencies}</strong> imports
            </span>
          </div>
        )}
      </div>

      {/* =========================================================================
          VIEW 1: SYSTEM ARCHITECTURE (Primary)
          ========================================================================= */}
      {activeTab === "system" && (
        <div className="arch-system-view">
          {/* Executive Architecture Summary Banner */}
          {graph.architecture && (
            <div className="arch-summary-banner">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", flexWrap: "wrap", gap: "0.5rem" }}>
                <div className="arch-summary-badge">
                  {graph.architecture.architecture_style || "SYSTEM DESIGN & ARCHITECTURE"}
                </div>
                <div className="gitdiagram-view-toggle">
                  <button
                    type="button"
                    className={`gitdiagram-btn ${systemLayoutMode === "gitdiagram" ? "active" : ""}`}
                    onClick={() => setSystemLayoutMode("gitdiagram")}
                    title="GitDiagram Interactive Architecture"
                  >
                    🎨 GitDiagram View
                  </button>
                  <button
                    type="button"
                    className={`gitdiagram-btn ${systemLayoutMode === "nodes" ? "active" : ""}`}
                    onClick={() => setSystemLayoutMode("nodes")}
                    title="Component Flow Cards"
                  >
                    🗂️ Card Flow
                  </button>
                </div>
              </div>
              <h3 className="arch-summary-title">{graph.architecture.title}</h3>
              <p className="arch-summary-text">{graph.architecture.summary}</p>
            </div>
          )}

          <div className="arch-stage-wrapper">
            <div className="arch-canvas-wrapper main-canvas" style={{ padding: systemLayoutMode === "gitdiagram" ? 0 : undefined, overflow: "hidden" }}>
              {hasSemanticArchitecture ? (
                systemLayoutMode === "gitdiagram" ? (
                  <MermaidDiagram
                    chart={compiledMermaidChart}
                    components={graph.architecture?.components || []}
                    selectedComponentId={selectedComponentId}
                    onSelectComponent={(id) => selectComponent(id)}
                  />
                ) : (
                  <ReactFlow
                    nodes={semanticNodes}
                    edges={semanticEdges}
                    nodeTypes={semanticNodeTypes}
                    edgeTypes={semanticEdgeTypes}
                    fitView
                    fitViewOptions={{ padding: 0.25 }}
                    minZoom={0.2}
                    maxZoom={2.0}
                    onPaneClick={clearSemanticSelection}
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background
                      color="var(--canvas-dots, #D5CABE)"
                      gap={24}
                      size={1.5}
                      variant={BackgroundVariant.Dots}
                    />
                    <Controls showInteractive={false} className="arch-controls" />
                  </ReactFlow>
                )
              ) : (
                <p className="empty">Generating architecture overview...</p>
              )}
            </div>

            {/* Explainability Side Drawer */}
            {selectedComponent && graph.architecture && (
              <ComponentDetailDrawer
                component={selectedComponent}
                relationships={graph.architecture.relationships || []}
                allComponents={graph.architecture.components || []}
                onClose={clearSemanticSelection}
              />
            )}
          </div>
        </div>
      )}


      {/* =========================================================================
          VIEW 2: RUNTIME EXECUTION FLOWS (Level 3 Deep Flow Explorer)
          ========================================================================= */}
      {activeTab === "flows" && (
        <div className="arch-flows-view">
          {flows.length === 0 ? (
            <p className="empty">No specific execution flows identified yet.</p>
          ) : (
            <div className="arch-flows-layout">
              {/* Left Column: Flow List Selector */}
              <aside className="arch-flows-sidebar">
                <p className="eyebrow" style={{ margin: "0 0 0.5rem" }}>
                  IDENTIFIED EXECUTION FLOWS
                </p>
                <div className="arch-flows-selector">
                  {flows.map((flow, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className={`arch-flow-selector-btn ${selectedFlowIndex === idx ? "active" : ""}`}
                      onClick={() => setSelectedFlowIndex(idx)}
                    >
                      <strong>{flow.name}</strong>
                      <span>{flow.steps.length} sequence steps</span>
                    </button>
                  ))}
                </div>
              </aside>

              {/* Right Column: Flow Sequence Stepper */}
              <main className="arch-flows-main">
                {flows[selectedFlowIndex] && (
                  <div className="arch-flow-detail-card">
                    <div className="arch-flow-header">
                      <span className="arch-flow-badge">END-TO-END FLOW</span>
                      <h3>{flows[selectedFlowIndex].name}</h3>
                      <p>{flows[selectedFlowIndex].description}</p>
                    </div>

                    <div className="arch-flow-steps-timeline">
                      {flows[selectedFlowIndex].steps.map((step, sIdx) => (
                        <div key={sIdx} className="arch-timeline-step">
                          <div className="timeline-marker">
                            <span className="step-circle">{sIdx + 1}</span>
                            {sIdx < flows[selectedFlowIndex].steps.length - 1 && (
                              <span className="timeline-line"></span>
                            )}
                          </div>
                          <div className="timeline-body">
                            <div className="timeline-component-pill">
                              {step.component.replace(/_/g, " ").toUpperCase()}
                            </div>
                            <h4 className="timeline-action">{step.action}</h4>
                            {(step.file || step.symbol) && (
                              <div className="timeline-meta">
                                {step.file && (
                                  <span className="timeline-file">
                                    <code>{step.file}</code>
                                  </span>
                                )}
                                {step.symbol && (
                                  <span className="timeline-symbol">
                                    symbol: <code>{step.symbol}</code>
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </main>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          VIEW 3: CODE DEPENDENCIES (Secondary)
          ========================================================================= */}
      {activeTab === "dependencies" && (
        <div className="arch-dependencies-view">
          <div className="arch-toolbar">
            <div className="arch-legend">
              <span className="legend-item">
                <span className="legend-swatch contains-swatch"></span>
                Folder hierarchy
              </span>
              <span className="legend-item">
                <span className="legend-swatch import-swatch"></span>
                File import
              </span>
            </div>

            {selectedFileId && (
              <div className="arch-selection-banner">
                <span>
                  Selected: <strong>{selectedFileId.replace("file:", "")}</strong>
                </span>
                <button
                  type="button"
                  className="arch-clear-btn"
                  onClick={clearFileSelection}
                >
                  Clear selection ✕
                </button>
              </div>
            )}
          </div>

          <div className="arch-canvas-wrapper">
            <ReactFlow
              nodes={fileNodes}
              edges={fileEdges}
              nodeTypes={fileNodeTypes}
              edgeTypes={fileEdgeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.15}
              maxZoom={2.5}
              onPaneClick={clearFileSelection}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                color="var(--canvas-dots, #D5CABE)"
                gap={24}
                size={1.5}
                variant={BackgroundVariant.Dots}
              />
              <Controls showInteractive={false} className="arch-controls" />
            </ReactFlow>
          </div>
        </div>
      )}
    </div>
  );
}
