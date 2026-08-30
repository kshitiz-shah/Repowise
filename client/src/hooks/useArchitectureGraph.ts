import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Node, Edge } from "@xyflow/react";
import type { Architecture } from "../api";
import { computeLayout } from "../services/elkLayout";

/* ------------------------------------------------------------------ */
/*  Public types used by the layout service and React Flow components  */
/* ------------------------------------------------------------------ */

export interface ArchGraphNode {
  id: string;
  label: string;
  nodeType: "folder" | "file";
  language?: string | null;
  path?: string | null;
  childrenCount?: number | null;
  linesOfCode?: number | null;
}

export interface ArchGraphEdge {
  source: string;
  target: string;
  type: "CONTAINS" | "IMPORTS";
}

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export function useArchitectureGraph(graph: Architecture) {
  // ---- Raw data parsed from API response ----
  const allNodes = useMemo<ArchGraphNode[]>(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        nodeType: n.type as "folder" | "file",
        language: n.language,
        path: n.path,
        childrenCount: n.children_count,
        linesOfCode: n.lines_of_code,
      })),
    [graph],
  );

  const allEdges = useMemo<ArchGraphEdge[]>(
    () =>
      graph.edges.map((e) => ({
        source: e.source,
        target: e.target,
        type: e.type as "CONTAINS" | "IMPORTS",
      })),
    [graph],
  );

  // ---- Expand / collapse state ----
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    // Start with top-level folders expanded (depth-1)
    const topLevel = new Set<string>();
    const hasParent = new Set<string>();
    for (const e of graph.edges) {
      if (e.type === "CONTAINS") hasParent.add(e.target);
    }
    for (const n of graph.nodes) {
      if (n.type === "folder" && !hasParent.has(n.id)) {
        topLevel.add(n.id);
      }
    }
    return topLevel;
  });

  const toggleFolder = useCallback((folderId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        // Collapse: also collapse all descendants
        const queue = [folderId];
        while (queue.length) {
          const id = queue.pop()!;
          next.delete(id);
          for (const e of graph.edges) {
            if (e.type === "CONTAINS" && e.source === id) {
              const target = graph.nodes.find((n) => n.id === e.target);
              if (target?.type === "folder") queue.push(e.target);
            }
          }
        }
      } else {
        next.add(folderId);
      }
      return next;
    });
  }, [graph]);

  // ---- Selection / highlighting ----
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  const selectFile = useCallback((fileId: string | null) => {
    setSelectedFileId((prev) => (prev === fileId ? null : fileId));
  }, []);

  const clearSelection = useCallback(() => setSelectedFileId(null), []);

  // Imports from / imports to the selected file
  const highlightState = useMemo(() => {
    if (!selectedFileId) return { importedBy: new Set<string>(), imports: new Set<string>(), relatedEdges: new Set<string>() };
    const imports = new Set<string>();
    const importedBy = new Set<string>();
    const relatedEdges = new Set<string>();
    for (const e of allEdges) {
      if (e.type !== "IMPORTS") continue;
      if (e.source === selectedFileId) {
        imports.add(e.target);
        relatedEdges.add(`${e.source}→${e.target}`);
      }
      if (e.target === selectedFileId) {
        importedBy.add(e.source);
        relatedEdges.add(`${e.source}→${e.target}`);
      }
    }
    return { imports, importedBy, relatedEdges };
  }, [selectedFileId, allEdges]);

  // Parent folder of selected file
  const selectedParentFolder = useMemo(() => {
    if (!selectedFileId) return null;
    const edge = allEdges.find((e) => e.type === "CONTAINS" && e.target === selectedFileId);
    return edge?.source ?? null;
  }, [selectedFileId, allEdges]);

  // ---- Compute visible nodes/edges based on expansion ----
  const { visibleNodes, visibleEdges } = useMemo(() => {
    const nodeById = new Map(allNodes.map((n) => [n.id, n]));

    // A node is visible if every ancestor folder in its CONTAINS chain is expanded
    const parentOf = new Map<string, string>();
    for (const e of allEdges) {
      if (e.type === "CONTAINS") parentOf.set(e.target, e.source);
    }

    function isVisible(id: string): boolean {
      const parent = parentOf.get(id);
      if (!parent) return true; // root-level node
      // Parent must itself be visible AND expanded
      return expanded.has(parent) && isVisible(parent);
    }

    const vNodes = allNodes.filter((n) => isVisible(n.id));
    const vIds = new Set(vNodes.map((n) => n.id));

    // Visible edges: CONTAINS edges between two visible nodes,
    // plus IMPORTS edges between visible nodes
    const vEdges = allEdges.filter(
      (e) => vIds.has(e.source) && vIds.has(e.target),
    );

    return { visibleNodes: vNodes, visibleEdges: vEdges };
  }, [allNodes, allEdges, expanded]);

  // ---- ELK Layout ----
  const [flowNodes, setFlowNodes] = useState<Node[]>([]);
  const [flowEdges, setFlowEdges] = useState<Edge[]>([]);
  const layoutVersion = useRef(0);

  useEffect(() => {
    const version = ++layoutVersion.current;

    computeLayout(visibleNodes, visibleEdges).then((result) => {
      if (version !== layoutVersion.current) return; // stale

      const nodes: Node[] = visibleNodes.map((n) => {
        const pos = result.nodes.get(n.id);
        const isFolder = n.nodeType === "folder";
        const isExpanded = expanded.has(n.id);
        return {
          id: n.id,
          type: isFolder ? "archFolder" : "archFile",
          position: { x: pos?.x ?? 0, y: pos?.y ?? 0 },
          data: {
            label: n.label,
            language: n.language,
            path: n.path,
            childrenCount: n.childrenCount,
            linesOfCode: n.linesOfCode,
            isExpanded,
            isSelected: n.id === selectedFileId,
            isHighlighted:
              n.id === selectedFileId ||
              highlightState.imports.has(n.id) ||
              highlightState.importedBy.has(n.id) ||
              n.id === selectedParentFolder,
            isDimmed: selectedFileId !== null &&
              n.id !== selectedFileId &&
              !highlightState.imports.has(n.id) &&
              !highlightState.importedBy.has(n.id) &&
              n.id !== selectedParentFolder,
            onToggle: isFolder ? () => toggleFolder(n.id) : undefined,
            onSelect: !isFolder ? () => selectFile(n.id) : undefined,
          },
          style: pos
            ? { width: pos.width, height: pos.height }
            : undefined,
        };
      });

      const edges: Edge[] = visibleEdges.map((e) => {
        const edgeId = `${e.source}→${e.target}`;
        const isImport = e.type === "IMPORTS";
        return {
          id: edgeId,
          source: e.source,
          target: e.target,
          type: isImport ? "archImport" : "archContains",
          animated: false,
          data: {
            isHighlighted: highlightState.relatedEdges.has(edgeId),
            isDimmed:
              selectedFileId !== null &&
              isImport &&
              !highlightState.relatedEdges.has(edgeId),
          },
        };
      });

      setFlowNodes(nodes);
      setFlowEdges(edges);
    });
  }, [visibleNodes, visibleEdges, expanded, selectedFileId, highlightState, selectedParentFolder, toggleFolder, selectFile]);

  return {
    flowNodes,
    flowEdges,
    selectedFileId,
    clearSelection,
    statistics: graph.statistics,
  };
}
