import ELK, { type ElkNode, type ElkExtendedEdge } from "elkjs/lib/elk.bundled.js";
import type { ArchGraphNode, ArchGraphEdge } from "../hooks/useArchitectureGraph";

const elk = new ELK();

export interface LayoutResult {
  nodes: Map<string, { x: number; y: number; width: number; height: number }>;
}

const NODE_WIDTH = 200;
const FILE_NODE_HEIGHT = 64;
const FOLDER_NODE_HEIGHT = 52;
const PADDING = 20;

/**
 * Runs ELK hierarchical layout on a flat list of visible nodes/edges.
 * Folders become compound (parent) nodes; files and subfolders are children.
 */
export async function computeLayout(
  nodes: ArchGraphNode[],
  edges: ArchGraphEdge[],
): Promise<LayoutResult> {
  // Build a lookup of visible node IDs
  const visibleIds = new Set(nodes.map((n) => n.id));

  // Build parent → children map from CONTAINS edges
  const parentMap = new Map<string, string>();
  for (const edge of edges) {
    if (edge.type === "CONTAINS" && visibleIds.has(edge.source) && visibleIds.has(edge.target)) {
      parentMap.set(edge.target, edge.source);
    }
  }

  // Collect root-level node IDs (those with no parent in visible set)
  const rootIds: string[] = [];
  for (const node of nodes) {
    if (!parentMap.has(node.id)) {
      rootIds.push(node.id);
    }
  }

  // Node lookup
  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  // Children lookup
  const childrenOf = new Map<string, string[]>();
  for (const [child, parent] of parentMap.entries()) {
    const list = childrenOf.get(parent) ?? [];
    list.push(child);
    childrenOf.set(parent, list);
  }

  // Recursively build the ELK tree
  function buildElkNode(id: string): ElkNode {
    const node = nodeById.get(id)!;
    const children = childrenOf.get(id);
    const isFolder = node.nodeType === "folder";
    const height = isFolder ? FOLDER_NODE_HEIGHT : FILE_NODE_HEIGHT;

    if (children && children.length > 0) {
      return {
        id,
        width: NODE_WIDTH,
        height,
        children: children.map(buildElkNode),
        layoutOptions: {
          "elk.padding": `[top=${height + PADDING},left=${PADDING},bottom=${PADDING},right=${PADDING}]`,
        },
      };
    }
    return { id, width: NODE_WIDTH, height };
  }

  // Filter IMPORTS edges to only those between visible nodes
  const elkEdges: ElkExtendedEdge[] = edges
    .filter((e) => e.type === "IMPORTS" && visibleIds.has(e.source) && visibleIds.has(e.target))
    .map((e) => ({ id: `${e.source}→${e.target}`, sources: [e.source], targets: [e.target] }));

  const graph: ElkNode = {
    id: "root",
    children: rootIds.map(buildElkNode),
    edges: elkEdges,
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.spacing.nodeNode": "40",
      "elk.layered.spacing.nodeNodeBetweenLayers": "60",
      "elk.layered.spacing.edgeNodeBetweenLayers": "30",
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.edgeRouting": "ORTHOGONAL",
    },
  };

  const laid = await elk.layout(graph);

  // Flatten the recursive result into an absolute-position map
  const result = new Map<string, { x: number; y: number; width: number; height: number }>();

  function collect(elkNode: ElkNode, offsetX: number, offsetY: number) {
    const x = (elkNode.x ?? 0) + offsetX;
    const y = (elkNode.y ?? 0) + offsetY;
    const w = elkNode.width ?? NODE_WIDTH;
    const h = elkNode.height ?? FILE_NODE_HEIGHT;
    result.set(elkNode.id, { x, y, width: w, height: h });
    for (const child of elkNode.children ?? []) {
      collect(child, x, y);
    }
  }

  for (const child of laid.children ?? []) {
    collect(child, 0, 0);
  }

  return { nodes: result };
}
