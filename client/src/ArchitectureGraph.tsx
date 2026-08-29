import type { Architecture } from "./api";

export default function ArchitectureGraph({ graph }: { graph: Architecture }) {
  if (!graph.nodes.length) return <p className="empty">No supported source files were found to map.</p>;
  const columns = Math.max(1, Math.ceil(Math.sqrt(graph.nodes.length)));
  const positions = new Map(graph.nodes.map((node, index) => [node.id, { x: 100 + (index % columns) * 230, y: 85 + Math.floor(index / columns) * 130 }]));
  const height = Math.max(260, Math.ceil(graph.nodes.length / columns) * 130 + 90);

  return <div className="graph-scroll"><div className="graph" style={{ minWidth: `${Math.max(640, columns * 230 + 100)}px`, height }}>
    <svg aria-hidden="true" viewBox={`0 0 ${Math.max(640, columns * 230 + 100)} ${height}`} preserveAspectRatio="none">
      <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" /></marker></defs>
      {graph.edges.map((edge) => { const from = positions.get(edge.source); const to = positions.get(edge.target); return from && to ? <line key={`${edge.source}-${edge.target}`} x1={from.x + 86} y1={from.y + 28} x2={to.x + 4} y2={to.y + 28} markerEnd="url(#arrow)" /> : null; })}
    </svg>
    {graph.nodes.map((node) => { const point = positions.get(node.id)!; return <div className="graph-node" style={{ left: point.x, top: point.y }} key={node.id}><span>{node.language}</span><strong>{node.label}</strong></div>; })}
  </div></div>;
}
