"""Render a theme map as Cypher, so a digest can be loaded into Neo4j.

The graph view already reads like a Neo4j result; this lets it actually become
one. The output is a single statement block that can be pasted straight into
Neo4j Browser or piped through cypher-shell.
"""

from __future__ import annotations

import re

from .models import ThemeMap

# Cypher identifiers cannot start with a digit and allow only word characters.
_NON_WORD = re.compile(r"\W+")
_LEADING_DIGIT = re.compile(r"^(?=\d)")

KIND_LABEL = {
    "core": "CoreIdea",
    "problem": "Problem",
    "method": "Method",
    "concept": "Concept",
    "evidence": "Evidence",
    "implication": "Implication",
}


def quote(value: str) -> str:
    """Escape a string for a single-quoted Cypher literal."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    # A literal newline would break the statement across lines.
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


def rel_type(label: str) -> str:
    """Turn 'is built from' into IS_BUILT_FROM."""
    cleaned = _NON_WORD.sub("_", label).strip("_").upper()
    return _LEADING_DIGIT.sub("R", cleaned) or "RELATED_TO"


def to_cypher(theme_map: ThemeMap, *, title: str | None = None) -> str:
    """Build the CREATE statement for a theme map."""
    used: set[str] = set()
    variables: dict[str, str] = {}

    lines: list[str] = []
    if title:
        lines.append(f"// {title}")
    lines.append(f"// {theme_map.core}")
    lines.append("")

    for node in theme_map.nodes:
        name = variable(node.id, used)
        variables[node.id] = name
        label = KIND_LABEL.get(node.kind, "Concept")
        lines.append(
            f"CREATE ({name}:Idea:{label} "
            f"{{id: {quote(node.id)}, name: {quote(node.label)}, "
            f"weight: {node.weight:g}, summary: {quote(node.blurb)}}})"
        )

    edges = [
        edge
        for edge in theme_map.edges
        if edge.source in variables and edge.target in variables
    ]
    if edges:
        lines.append("")
        for edge in edges:
            source = variables[edge.source]
            target = variables[edge.target]
            lines.append(
                f"CREATE ({source})-[:{rel_type(edge.label)} "
                f"{{label: {quote(edge.label)}}}]->({target})"
            )

    return "\n".join(lines) + "\n"
