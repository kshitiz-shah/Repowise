import { useEffect, useRef, useState, useCallback } from "react";
import type { Node, Edge } from "@xyflow/react";
import ELK, { type ElkNode, type ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";

import type { ArchitectureComponent, SemanticArchitecture } from "../api";

const elk = new ELK();

const COMPONENT_WIDTH = 260;
const COMPONENT_HEIGHT = 135;

export function useSemanticArchitecture(architecture?: SemanticArchitecture) {
  const [flowNodes, setFlowNodes] = useState<Node[]>([]);
  const [flowEdges, setFlowEdges] = useState<Edge[]>([]);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const layoutVersion = useRef(0);

  const selectComponent = useCallback((id: string | null) => {
    setSelectedComponentId((prev) => (prev === id ? null : id));
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedComponentId(null);
  }, []);

  useEffect(() => {
    if (!architecture || !architecture.components || architecture.components.length === 0) {
      setFlowNodes([]);
      setFlowEdges([]);
      return;
    }

    const version = ++layoutVersion.current;
    const components = architecture.components;
    const relationships = architecture.relationships || [];

    const elkNodes: ElkNode[] = components.map((comp) => ({
      id: comp.id,
      width: COMPONENT_WIDTH,
      height: COMPONENT_HEIGHT,
    }));

    const elkEdges: ElkExtendedEdge[] = relationships.map((rel, index) => ({
      id: `rel-${index}-${rel.source}->${rel.target}`,
      sources: [rel.source],
      targets: [rel.target],
    }));

    const elkGraph: ElkNode = {
      id: "semantic-root",
      children: elkNodes,
      edges: elkEdges,
      layoutOptions: {
        "elk.algorithm": "layered",
        "elk.direction": "DOWN",
        "elk.spacing.nodeNode": "60",
        "elk.layered.spacing.nodeNodeBetweenLayers": "90",
        "elk.layered.spacing.edgeNodeBetweenLayers": "40",
        "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
        "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
        "elk.edgeRouting": "SPLINES",
      },
    };

    elk.layout(elkGraph).then((laid) => {
      if (version !== layoutVersion.current) return;

      const posMap = new Map<string, { x: number; y: number }>();
      for (const child of laid.children || []) {
        posMap.set(child.id, { x: child.x || 0, y: child.y || 0 });
      }

      const nodes: Node[] = components.map((comp) => {
        const pos = posMap.get(comp.id) || { x: 0, y: 0 };
        return {
          id: comp.id,
          type: "semanticComponent",
          position: pos,
          data: {
            id: comp.id,
            name: comp.name,
            type: comp.type,
            description: comp.description,
            fileCount: comp.files?.length || 0,
            isSelected: comp.id === selectedComponentId,
            onSelect: () => selectComponent(comp.id),
          },
          style: { width: COMPONENT_WIDTH, height: COMPONENT_HEIGHT },
        };
      });

      const edges: Edge[] = relationships.map((rel, index) => {
        const edgeId = `rel-${index}-${rel.source}->${rel.target}`;
        return {
          id: edgeId,
          source: rel.source,
          target: rel.target,
          type: "semanticRelationship",
          data: {
            label: rel.label,
            type: rel.type,
            description: rel.description,
            isSelected:
              selectedComponentId !== null &&
              (rel.source === selectedComponentId || rel.target === selectedComponentId),
          },
        };
      });

      setFlowNodes(nodes);
      setFlowEdges(edges);
    });
  }, [architecture, selectedComponentId, selectComponent]);

  const selectedComponent: ArchitectureComponent | null =
    architecture?.components.find((c) => c.id === selectedComponentId) || null;

  return {
    flowNodes,
    flowEdges,
    selectedComponent,
    selectedComponentId,
    selectComponent,
    clearSelection,
  };
}
