import React from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface FolderNodeData {
  label: string;
  path?: string | null;
  childrenCount?: number | null;
  isExpanded?: boolean;
  isDimmed?: boolean;
  isHighlighted?: boolean;
  onToggle?: () => void;
  [key: string]: unknown;
}

export const FolderNode: React.FC<NodeProps> = ({ data }) => {
  const nodeData = data as unknown as FolderNodeData;
  const isExpanded = nodeData.isExpanded ?? false;
  const childrenCount = nodeData.childrenCount ?? 0;

  return (
    <div
      className={`arch-node arch-folder-node ${nodeData.isDimmed ? "dimmed" : ""} ${nodeData.isHighlighted ? "highlighted" : ""}`}
      onClick={(e) => {
        e.stopPropagation();
        nodeData.onToggle?.();
      }}
    >
      <Handle type="target" position={Position.Top} className="arch-handle" />
      <div className="arch-folder-header">
        <div className="arch-folder-badge">
          <span className="arch-type-tag">📁 FOLDER</span>
          <span className="arch-count-tag">{childrenCount} items</span>
        </div>
        <button
          type="button"
          className="arch-toggle-btn"
          onClick={(e) => {
            e.stopPropagation();
            nodeData.onToggle?.();
          }}
          title={isExpanded ? "Collapse folder" : "Expand folder"}
        >
          {isExpanded ? "−" : "+"}
        </button>
      </div>
      <div className="arch-node-title" title={nodeData.path ?? nodeData.label}>
        {nodeData.label}
      </div>
      <Handle type="source" position={Position.Bottom} className="arch-handle" />
    </div>
  );
};
