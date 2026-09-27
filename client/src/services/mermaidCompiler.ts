import type { ArchitectureComponent, ArchitectureGroup, ArchitectureRelationship, SemanticArchitecture } from "../api";

export function escapeMermaidText(text: string): string {
  if (!text) return "";
  const cleaned = String(text)
    .replace(/[\r\n\t]+/g, " ")
    .replace(/"/g, "&quot;")
    .replace(/`/g, "&#96;")
    .replace(/\\/g, "&#92;")
    .replace(/\|/g, "&#124;")
    .replace(/\[/g, "&#91;")
    .replace(/\]/g, "&#93;")
    .replace(/\{/g, "&#123;")
    .replace(/\}/g, "&#125;")
    .replace(/\(/g, "&#40;")
    .replace(/\)/g, "&#41;")
    .trim();
  return cleaned || "Unnamed";
}

export function mermaidNodeId(nodeId: string): string {
  const clean = String(nodeId).replace(/[^a-zA-Z0-9_]/g, "_");
  return `node_${clean}`;
}

export function mermaidGroupId(groupId: string): string {
  const clean = String(groupId).replace(/[^a-zA-Z0-9_]/g, "_");
  return `group_${clean}`;
}

export function renderMermaidNode(comp: ArchitectureComponent): string {
  const nodeId = mermaidNodeId(comp.id);
  const label = escapeMermaidText(comp.name || comp.id);
  let shape = (comp.shape || "box").toLowerCase();

  const words = `${comp.name} ${comp.type} ${comp.id}`.toLowerCase();
  if (shape === "box") {
    if (
      words.includes("database") ||
      words.includes("storage") ||
      words.includes("cache") ||
      words.includes("postgres") ||
      words.includes("qdrant") ||
      words.includes("redis") ||
      words.includes("prisma")
    ) {
      shape = "database";
    } else if (
      words.includes("actor") ||
      words.includes("user") ||
      words.includes("browser") ||
      words.includes("client")
    ) {
      shape = "circle";
    } else if (
      words.includes("queue") ||
      words.includes("worker") ||
      words.includes("event")
    ) {
      shape = "queue";
    }
  }

  let fileHint = "";
  if (comp.files && comp.files.length > 0) {
    const firstFile = comp.files[0].split("/").pop();
    if (firstFile && firstFile.length <= 22) {
      fileHint = `<br/>[${escapeMermaidText(firstFile)}]`;
    }
  }

  const nodeLabel = `${label}${fileHint}`;

  switch (shape) {
    case "database":
      return `${nodeId}[("${nodeLabel}")]`;
    case "circle":
      return `${nodeId}(("${nodeLabel}"))`;
    case "hexagon":
      return `${nodeId}{{"${nodeLabel}"}}`;
    case "queue":
    case "box":
    default:
      return `${nodeId}["${nodeLabel}"]`;
  }
}

export function renderMermaidEdge(rel: ArchitectureRelationship): string {
  const fromId = mermaidNodeId(rel.source);
  const toId = mermaidNodeId(rel.target);
  const isDashed =
    rel.style === "dashed" ||
    rel.type?.toUpperCase() === "ASYNC" ||
    rel.type?.toUpperCase() === "OPTIONAL" ||
    rel.type?.toUpperCase() === "EVENT";
  const connector = isDashed ? "-.->" : "-->";

  if (rel.label) {
    const label = escapeMermaidText(rel.label);
    return `${fromId} ${connector}|"${label}"| ${toId}`;
  }
  return `${fromId} ${connector} ${toId}`;
}

export function getNodeToneClass(comp: ArchitectureComponent, groupIdx?: number): string {
  const words = `${comp.name} ${comp.type} ${comp.id}`.toLowerCase();
  if (
    comp.shape === "database" ||
    words.includes("database") ||
    words.includes("storage") ||
    words.includes("cache") ||
    words.includes("postgres") ||
    words.includes("sqlite") ||
    words.includes("redis") ||
    words.includes("qdrant") ||
    words.includes("prisma")
  ) {
    return "toneAmber";
  }
  if (
    comp.shape === "queue" ||
    words.includes("queue") ||
    words.includes("worker") ||
    words.includes("background") ||
    words.includes("scheduler") ||
    words.includes("task")
  ) {
    return "toneRose";
  }
  if (
    words.includes("client") ||
    words.includes("browser") ||
    words.includes("user") ||
    words.includes("frontend") ||
    words.includes("view") ||
    words.includes("react") ||
    words.includes("ui") ||
    words.includes("actor")
  ) {
    return "toneBlue";
  }
  if (
    words.includes("api") ||
    words.includes("server") ||
    words.includes("route") ||
    words.includes("controller") ||
    words.includes("express") ||
    words.includes("fastapi") ||
    words.includes("gateway") ||
    words.includes("auth")
  ) {
    return "toneMint";
  }
  if (
    words.includes("llm") ||
    words.includes("ai") ||
    words.includes("model") ||
    words.includes("inference") ||
    words.includes("rag") ||
    words.includes("embedding") ||
    words.includes("vector")
  ) {
    return "toneIndigo";
  }
  return "toneTeal";
}

export function compileClientMermaidArchitecture(architecture: SemanticArchitecture): string {
  const lines: string[] = ["flowchart TD"];
  const groupedNodeIds = new Set<string>();
  const classAssignments: Record<string, string[]> = {
    toneBlue: [],
    toneAmber: [],
    toneMint: [],
    toneRose: [],
    toneIndigo: [],
    toneTeal: [],
    toneNeutral: [],
  };

  const groups = architecture.groups || [];
  const components = architecture.components || [];
  const relationships = architecture.relationships || [];

  const groupMap = new Map<string, ArchitectureComponent[]>();
  for (const g of groups) {
    groupMap.set(g.id, []);
  }

  const ungroupedComponents: ArchitectureComponent[] = [];
  for (const comp of components) {
    const gId = comp.group_id || comp.groupId;
    if (gId && groupMap.has(gId)) {
      groupMap.get(gId)!.push(comp);
    } else {
      ungroupedComponents.push(comp);
    }

  }

  // Render Subgraph Groups
  for (let gIdx = 0; gIdx < groups.length; gIdx++) {
    const g = groups[gIdx];
    const gComps = groupMap.get(g.id) || [];
    if (gComps.length === 0) continue;

    lines.push("");
    lines.push(`subgraph ${mermaidGroupId(g.id)}["${escapeMermaidText(g.label)}"]`);
    for (const comp of gComps) {
      lines.push(`  ${renderMermaidNode(comp)}`);
      groupedNodeIds.add(comp.id);
      const tone = getNodeToneClass(comp, gIdx);
      if (!classAssignments[tone]) classAssignments[tone] = [];
      classAssignments[tone].push(mermaidNodeId(comp.id));
    }
    lines.push("end");
  }

  // Render Ungrouped Nodes
  const remComps = ungroupedComponents.filter((c) => !groupedNodeIds.has(c.id));
  if (remComps.length > 0) {
    lines.push("");
    for (const comp of remComps) {
      lines.push(renderMermaidNode(comp));
      const tone = getNodeToneClass(comp);
      if (!classAssignments[tone]) classAssignments[tone] = [];
      classAssignments[tone].push(mermaidNodeId(comp.id));
    }
  }

  // Render Relationships
  if (relationships.length > 0) {
    lines.push("");
    for (const rel of relationships) {
      if (rel.source && rel.target) {
        lines.push(renderMermaidEdge(rel));
      }
    }
  }

  // Color Tone Definitions (GitDiagram theme tokens)
  lines.push("");
  lines.push("classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a;");
  lines.push("classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554;");
  lines.push("classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f;");
  lines.push("classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d;");
  lines.push("classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337;");
  lines.push("classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81;");
  lines.push("classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a;");

  for (const [className, nodeIds] of Object.entries(classAssignments)) {
    if (nodeIds && nodeIds.length > 0) {
      lines.push(`class ${nodeIds.join(",")} ${className};`);
    }
  }

  return lines.join("\n").trim();
}
