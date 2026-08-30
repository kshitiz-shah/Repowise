import React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface ComponentNodeData {
  id: string;
  name: string;
  type: string;
  description: string;
  fileCount: number;
  isSelected?: boolean;
  onSelect?: () => void;
  [key: string]: unknown;
}

const TYPE_ICONS: Record<string, string> = {
  frontend: "🌐",
  client: "💻",
  api: "⚡",
  backend: "🖥️",
  service: "⚙️",
  microservice: "🧩",
  authentication: "🔐",
  auth: "🔐",
  database: "🗄️",
  data_access: "🧱",
  storage: "📦",
  cache: "⚡",
  queue: "📬",
  worker: "⏳",
  scheduler: "⏱️",
  external_service: "☁️",
  middleware: "🛡️",
  infrastructure: "🏗️",
  business_logic: "🧠",
  library: "📚",
  custom: "📦",
};

export const ComponentNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as ComponentNodeData;
  const icon = TYPE_ICONS[nodeData.type.toLowerCase()] || "⚙️";
  const typeLabel = nodeData.type.replace(/_/g, " ").toUpperCase();

  return (
    <div
      className={`arch-component-card ${nodeData.isSelected ? "selected" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        nodeData.onSelect?.();
      }}
      title="Click to view component details, files, and evidence"
    >
      <Handle type="target" position={Position.Top} className="arch-handle" />
      <Handle type="target" position={Position.Left} className="arch-handle" />

      {/* Header with Type badge and file count */}
      <div className="arch-comp-header">
        <span className="arch-comp-type-badge">
          <span className="arch-comp-icon">{icon}</span>
          <span>{typeLabel}</span>
        </span>
        {nodeData.fileCount > 0 && (
          <span className="arch-comp-files-badge">{nodeData.fileCount} files</span>
        )}
      </div>

      {/* Component Title */}
      <div className="arch-comp-name">{nodeData.name}</div>

      {/* Short Human Description */}
      {nodeData.description && (
        <p className="arch-comp-desc">{nodeData.description}</p>
      )}

      <div className="arch-comp-footer">
        <span className="arch-comp-inspect-hint">Click to inspect ↗</span>
      </div>

      <Handle type="source" position={Position.Bottom} className="arch-handle" />
      <Handle type="source" position={Position.Right} className="arch-handle" />
    </div>
  );
};
