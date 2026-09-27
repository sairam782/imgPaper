"""Render the derived paper graph as Cypher, so a digest can become a Neo4j database.

The graph view already reads like a Neo4j result; this lets it actually be one.
The output is a single block that can be pasted into Neo4j Browser or piped
through cypher-shell.
"""

from __future__ import annotations

import re

from .graph_model import PaperGraph

# Cypher identifiers cannot start with a digit and allow only word characters.
_NON_WORD = re.compile(r"\W+")
_LEADING_DIGIT = re.compile(r"^(?=\d)")


def quote(value: str) -> str:
    """Escape a string for a single-quoted Cypher literal."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return "'" + escaped.replace("\n", "\\n").replace("\r", "") + "'"


def variable(node_id: str, used: set[str]) -> str:
    """A safe, unique Cypher variable for a node id."""
    base = _NON_WORD.sub("_", node_id).strip("_") or "n"
    base = _LEADING_DIGIT.sub("n", base)

    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _props(pairs: dict[str, str | float | int]) -> str:
    rendered = []
    for key, value in pairs.items():
        safe_key = _NON_WORD.sub("_", key).strip("_") or "prop"
        safe_key = _LEADING_DIGIT.sub("p", safe_key)
        if isinstance(value, (int, float)):
            rendered.append(f"{safe_key}: {value:g}")
        else:
            rendered.append(f"{safe_key}: {quote(value)}")
    return "{" + ", ".join(rendered) + "}"


def to_cypher(graph: PaperGraph, *, title: str | None = None) -> str:
    """Build the CREATE statements for a whole paper graph."""
    used: set[str] = set()
    variables: dict[str, str] = {}

    lines: list[str] = []
    if title:
        lines.append(f"// {title}")
    lines.append(f"// {len(graph.nodes)} nodes, {len(graph.edges)} relationships")
    lines.append("")

    for node in graph.nodes:
        name = variable(node.id, used)
        variables[node.id] = name
        pairs: dict[str, str | float | int] = {
            "id": node.id,
            "name": node.label,
            "weight": round(node.weight, 3),
            "degree": node.degree,
        }
        if node.blurb:
            pairs["summary"] = node.blurb
        pairs.update(node.props)
        lines.append(f"CREATE ({name}:{node.kind} {_props(pairs)})")

    if graph.edges:
        lines.append("")
        for edge in graph.edges:
            source = variables.get(edge.source)
            target = variables.get(edge.target)
            if not source or not target:
                continue
            pairs: dict[str, str | float | int] = {"label": edge.label}
            if edge.derived:
                pairs["derived"] = "true"
            lines.append(f"CREATE ({source})-[:{edge.type} {_props(pairs)}]->({target})")

    return "\n".join(lines) + "\n"
