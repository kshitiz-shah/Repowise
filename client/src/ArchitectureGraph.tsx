import React, { useState, useMemo } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  type NodeTypes,
  type EdgeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { Architecture } from "./api";
import { useSemanticArchitecture } from "./hooks/useSemanticArchitecture";
import { useArchitectureGraph } from "./hooks/useArchitectureGraph";
import { ComponentNode } from "./components/architecture/ComponentNode";
import { SemanticEdge } from "./components/architecture/SemanticEdge";
import { ComponentDetailDrawer } from "./components/architecture/ComponentDetailDrawer";
import { FolderNode } from "./components/architecture/FolderNode";
import { FileNode } from "./components/architecture/FileNode";
import { ContainsEdge } from "./components/architecture/ContainsEdge";
import { ImportEdge } from "./components/architecture/ImportEdge";

const semanticNodeTypes: NodeTypes = {
  semanticComponent: ComponentNode,
};

const semanticEdgeTypes: EdgeTypes = {
  semanticRelationship: SemanticEdge,
};

const fileNodeTypes: NodeTypes = {
  archFolder: FolderNode,
  archFile: FileNode,
};

const fileEdgeTypes: EdgeTypes = {
  archContains: ContainsEdge,
  archImport: ImportEdge,
};

interface ArchitectureGraphProps {
  graph: Architecture;
}

export default function ArchitectureGraph({ graph }: ArchitectureGraphProps) {
  const [activeTab, setActiveTab] = useState<"system" | "dependencies">("system");

  // Semantic Architecture hook (Primary view)
  const {
    flowNodes: semanticNodes,
    flowEdges: semanticEdges,
    selectedComponent,
    clearSelection: clearSemanticSelection,
  } = useSemanticArchitecture(graph.architecture);

  // File Dependency Graph hook (Secondary view)
  const {
    flowNodes: fileNodes,
    flowEdges: fileEdges,
    selectedFileId,
    clearSelection: clearFileSelection,
    statistics,
  } = useArchitectureGraph(graph);

  const selectedFileNode = useMemo(() => {
    if (!selectedFileId) return null;
    return graph.nodes.find((n) => n.id === selectedFileId);
  }, [selectedFileId, graph.nodes]);

  const hasSemanticArchitecture = Boolean(
    graph.architecture &&
      graph.architecture.components &&
      graph.architecture.components.length > 0,
  );

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
            markerWidth="12"
            markerHeight="12"
            refX="9"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path
              d="M1,1 L1,7 L9,4 z"
              fill="#f8fafc"
              stroke="#0284c7"
              strokeWidth="1"
            />
          </marker>

          {/* File Dependency Graph Arrows */}
          <marker
            id="arch-arrow-default"
            markerWidth="12"
            markerHeight="12"
            refX="9"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path
              d="M1,1 L1,7 L9,4 z"
              fill="#f8fafc"
              stroke="#475569"
              strokeWidth="1"
            />
          </marker>
          <marker
            id="arch-arrow-highlight"
            markerWidth="14"
            markerHeight="14"
            refX="10"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path
              d="M1,1 L1,7 L10,4 z"
              fill="#38bdf8"
              stroke="#0284c7"
              strokeWidth="1"
            />
          </marker>
          <marker
            id="arch-arrow-dim"
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="4"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M1,1 L1,7 L8,4 z" fill="#64748b" opacity="0.4" />
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
            🏛️ System Architecture
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
              <div className="arch-summary-badge">ARCHITECTURAL OVERVIEW</div>
              <h3 className="arch-summary-title">{graph.architecture.title}</h3>
              <p className="arch-summary-text">{graph.architecture.summary}</p>
            </div>
          )}

          <div className="arch-stage-wrapper">
            <div className="arch-canvas-wrapper main-canvas">
              {hasSemanticArchitecture ? (
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
                    color="#94a3b8"
                    gap={24}
                    size={1.5}
                    variant={BackgroundVariant.Dots}
                  />
                  <Controls showInteractive={false} className="arch-controls" />
                </ReactFlow>
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
          VIEW 2: CODE DEPENDENCIES (Secondary)
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

            {selectedFileNode && (
              <div className="arch-selection-banner">
                <span>
                  Selected: <strong>{selectedFileNode.path || selectedFileNode.label}</strong>
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
                color="#94a3b8"
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
