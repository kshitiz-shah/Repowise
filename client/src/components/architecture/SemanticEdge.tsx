import React from "react";
import { getBezierPath, EdgeLabelRenderer, type EdgeProps } from "@xyflow/react";

export interface SemanticEdgeData {
  label?: string;
  description?: string | null;
  type?: string;
  isSelected?: boolean;
  [key: string]: unknown;
}

export const SemanticEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const edgeData = (data as unknown as SemanticEdgeData) || {};
  const label = edgeData.label || edgeData.type || "";

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.2,
  });

  return (
    <>
      <path
        id={id}
        className="arch-semantic-edge"
        d={edgePath}
        fill="none"
        markerEnd="url(#arch-semantic-arrow)"
      />

      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "all",
            }}
            className="arch-semantic-edge-label"
            title={edgeData.description || `${label} relationship`}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};
