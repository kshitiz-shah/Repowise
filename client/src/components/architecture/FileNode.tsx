import React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface FileNodeData {
  label: string;
  language?: string | null;
  path?: string | null;
  linesOfCode?: number | null;
  isSelected?: boolean;
  isHighlighted?: boolean;
  isDimmed?: boolean;
  onSelect?: () => void;
  [key: string]: unknown;
}

export const FileNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as FileNodeData;
  const language = (nodeData.language || "code").toUpperCase();

  return (
    <div
      className={`arch-node arch-file-node ${nodeData.isSelected ? "selected" : ""} ${
        nodeData.isHighlighted ? "highlighted" : ""
      } ${nodeData.isDimmed ? "dimmed" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        nodeData.onSelect?.();
      }}
    >
      <Handle type="target" position={Position.Top} className="arch-handle" />
      <div className="arch-file-header">
        <span className="arch-lang-tag">{language}</span>
        {nodeData.linesOfCode ? (
          <span className="arch-loc-tag">{nodeData.linesOfCode} loc</span>
        ) : null}
      </div>
      <div className="arch-node-title" title={nodeData.path ?? nodeData.label}>
        {nodeData.label}
      </div>
      <Handle type="source" position={Position.Bottom} className="arch-handle" />
    </div>
  );
};
