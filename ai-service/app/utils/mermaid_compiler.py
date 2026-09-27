import re
from typing import Any
from app.api.schemas.architecture import ArchitectureComponent, ArchitectureGroup, ArchitectureRelationship, SemanticArchitecture


def escape_mermaid_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[\r\n\t]+", " ", str(text))
    cleaned = (
        cleaned.replace('"', "&quot;")
        .replace("`", "&#96;")
        .replace("\\", "&#92;")
        .replace("|", "&#124;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("{", "&#123;")
        .replace("}", "&#125;")
        .replace("(", "&#40;")
        .replace(")", "&#41;")
        .strip()
    )
    return cleaned or "Unnamed"


def mermaid_node_id(node_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", str(node_id))
    return f"node_{clean}"


def mermaid_group_id(group_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", str(group_id))
    return f"group_{clean}"


def render_mermaid_node(comp: ArchitectureComponent) -> str:
    node_id = mermaid_node_id(comp.id)
    label = escape_mermaid_text(comp.name or comp.id)
    shape = (comp.shape or "box").lower()

    # If shape not explicitly set, deduce from type / name
    words = f"{comp.name} {comp.type} {comp.id}".lower()
    if shape == "box":
        if "database" in words or "storage" in words or "cache" in words or "postgres" in words or "qdrant" in words or "redis" in words:
            shape = "database"
        elif "actor" in words or "user" in words or "browser" in words or "client" in words:
            shape = "circle"
        elif "queue" in words or "worker" in words or "event" in words:
            shape = "queue"

    file_hint = ""
    if comp.files and len(comp.files) > 0:
        first_file = comp.files[0].split("/")[-1]
        if first_file and len(first_file) <= 24:
            file_hint = f"<br/>[{escape_mermaid_text(first_file)}]"

    node_label = f"{label}{file_hint}"

    if shape == "database":
        return f'{node_id}[("{node_label}")]'
    elif shape == "circle":
        return f'{node_id}(("{node_label}"))'
    elif shape == "hexagon":
        return f'{node_id}{{"{node_label}"}}'
    else:
        return f'{node_id}["{node_label}"]'


def render_mermaid_edge(rel: ArchitectureRelationship) -> str:
    from_id = mermaid_node_id(rel.source)
    to_id = mermaid_node_id(rel.target)
    is_dashed = getattr(rel, "style", "solid") == "dashed" or rel.type.upper() in ("ASYNC", "OPTIONAL", "EVENT")
    connector = "-.->" if is_dashed else "-->"

    if rel.label:
        label = escape_mermaid_text(rel.label)
        return f'{from_id} {connector}|"{label}"| {to_id}'
    return f"{from_id} {connector} {to_id}"


def get_node_tone_class(comp: ArchitectureComponent, group_idx: int | None = None) -> str:
    words = f"{comp.name} {comp.type} {comp.id}".lower()
    if comp.shape == "database" or any(w in words for w in ["database", "storage", "cache", "postgres", "sqlite", "redis", "qdrant", "prisma"]):
        return "toneAmber"
    if comp.shape == "queue" or any(w in words for w in ["queue", "worker", "background", "scheduler", "task"]):
        return "toneRose"
    if any(w in words for w in ["client", "browser", "user", "frontend", "view", "react", "ui", "actor"]):
        return "toneBlue"
    if any(w in words for w in ["api", "server", "route", "controller", "express", "fastapi", "gateway", "auth"]):
        return "toneMint"
    if any(w in words for w in ["llm", "ai", "model", "inference", "rag", "embedding", "vector"]):
        return "toneIndigo"
    return "toneTeal"


def compile_mermaid_architecture(architecture: SemanticArchitecture) -> str:
    lines: list[str] = ["flowchart TD"]
    grouped_node_ids: set[str] = set()
    class_assignments: dict[str, list[str]] = {
        "toneBlue": [],
        "toneAmber": [],
        "toneMint": [],
        "toneRose": [],
        "toneIndigo": [],
        "toneTeal": [],
        "toneNeutral": [],
    }

    groups = architecture.groups or []
    components = architecture.components or []
    relationships = architecture.relationships or []

    # Map groups
    group_map: dict[str, list[ArchitectureComponent]] = {}
    for g in groups:
        group_map[g.id] = []

    ungrouped_components: list[ArchitectureComponent] = []
    for comp in components:
        g_id = comp.group_id or getattr(comp, "groupId", None)
        if g_id and g_id in group_map:
            group_map[g_id].append(comp)
        else:
            ungrouped_components.append(comp)

    # Render groups
    for g_idx, g in enumerate(groups):
        g_comps = group_map.get(g.id, [])
        if not g_comps:
            continue
        lines.append("")
        lines.append(f'subgraph {mermaid_group_id(g.id)}["{escape_mermaid_text(g.label)}"]')
        for comp in g_comps:
            lines.append(f"  {render_mermaid_node(comp)}")
            grouped_node_ids.add(comp.id)
            tone = get_node_tone_class(comp, g_idx)
            class_assignments[tone].append(mermaid_node_id(comp.id))
        lines.append("end")

    # Render ungrouped
    rem_comps = [c for c in ungrouped_components if c.id not in grouped_node_ids]
    if rem_comps:
        lines.append("")
        for comp in rem_comps:
            lines.append(render_mermaid_node(comp))
            tone = get_node_tone_class(comp)
            class_assignments[tone].append(mermaid_node_id(comp.id))

    # Render relationships
    if relationships:
        lines.append("")
        for rel in relationships:
            if rel.source and rel.target:
                lines.append(render_mermaid_edge(rel))

    # Add Click Events to components that have files or paths
    clickable_nodes = [c for c in components if c.files and len(c.files) > 0]
    if clickable_nodes:
        lines.append("")
        for c in clickable_nodes:
            # We add click callbacks
            lines.append(f'click {mermaid_node_id(c.id)} call onComponentNodeClick("{c.id}")')

    # Color Tone Definitions matching GitDiagram & RepoWise modern aesthetics
    lines.append("")
    lines.append("classDef toneNeutral fill:#f8fafc,stroke:#334155,stroke-width:1.5px,color:#0f172a;")
    lines.append("classDef toneBlue fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px,color:#172554;")
    lines.append("classDef toneAmber fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f;")
    lines.append("classDef toneMint fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px,color:#14532d;")
    lines.append("classDef toneRose fill:#ffe4e6,stroke:#e11d48,stroke-width:1.5px,color:#881337;")
    lines.append("classDef toneIndigo fill:#e0e7ff,stroke:#4f46e5,stroke-width:1.5px,color:#312e81;")
    lines.append("classDef toneTeal fill:#ccfbf1,stroke:#0f766e,stroke-width:1.5px,color:#134e4a;")

    for tone, node_ids in class_assignments.items():
        if node_ids:
            lines.append(f"class {','.join(node_ids)} {tone};")

    return "\n".join(lines).strip()
