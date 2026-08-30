import React from "react";
import { getSmoothStepPath, type EdgeProps } from "@xyflow/react";

export const ContainsEdge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
}) => {
  const [edgePath] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8,
  });

  return (
    <path
      id={id}
      className="arch-contains-edge"
      d={edgePath}
      style={{
        stroke: "#94a3b8",
        strokeWidth: 1.5,
        strokeDasharray: "4 4",
        fill: "none",
        ...style,
      }}
    />
  );
};
