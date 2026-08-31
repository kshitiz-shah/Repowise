import React from "react";
import { getBezierPath, type EdgeProps } from "@xyflow/react";

export interface ImportEdgeData {
  isHighlighted?: boolean;
  isDimmed?: boolean;
  [key: string]: unknown;
}

export const ImportEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}) => {
  const edgeData = (data as unknown as ImportEdgeData) || {};
  const isHighlighted = edgeData.isHighlighted ?? false;
  const isDimmed = edgeData.isDimmed ?? false;

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.25,
  });

  const markerId = isHighlighted
    ? "arch-arrow-highlight"
    : isDimmed
    ? "arch-arrow-dim"
    : "arch-arrow-default";

  return (
    <g className={`arch-import-edge-group ${isHighlighted ? "highlighted" : ""} ${isDimmed ? "dimmed" : ""}`}>
      {/* Background stroke for hand-drawn marker glow effect when highlighted */}
      {isHighlighted && (
        <path
          d={edgePath}
          fill="none"
          stroke="#C56A3C"
          strokeWidth={5}
          strokeOpacity={0.25}
          strokeLinecap="round"
        />
      )}
      <path
        id={id}
        className={`arch-import-edge ${isHighlighted ? "highlighted" : ""} ${isDimmed ? "dimmed" : ""}`}
        d={edgePath}
        fill="none"
        markerEnd={`url(#${markerId})`}
      />
    </g>
  );
};
