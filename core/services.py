from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

DECOMPOSITION_SYSTEM = """\
You are a cognitive architect. Your sole task is to decompose a learning goal \
into a directed acyclic graph of prerequisite concepts.

RULES:
1. Every node MUST have a strictly lowercase dot-separated namespace \
   (e.g. cisce.icse.chemistry.redox.oxidation_state).
2. The root node's namespace must begin with the user-supplied root_namespace prefix.
3. Edges point FROM a prerequisite TO the concept that depends on it \
   (e.g. oxidation_state → redox means redox requires oxidation_state).
4. Output ONLY valid JSON matching the schema below. No markdown fences, no prose.

OUTPUT SCHEMA:
{
  "nodes": [
    {
      "namespace": "string",
      "label": "string",
      "summary": "string (one paragraph, plain English)"
    }
  ],
  "edges": [
    {
      "source": "string (namespace of prerequisite)",
      "target": "string (namespace of dependent concept)",
      "weight": 0.0 to 1.0
    }
  ]
}
"""


def build_user_prompt(goal_title: str, root_namespace: str, user_text: str) -> str:
    return (
        f"Goal: {goal_title}\n"
        f"Root namespace prefix: {root_namespace}\n\n"
        f"User's description of what they want to learn:\n"
        f"---\n{user_text}\n---\n\n"
        f"Decompose this into a directed acyclic graph of prerequisite concepts."
    )


def decompose_to_graph(
    goal_title: str,
    root_namespace: str,
    user_text: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call OpenRouter and return parsed {nodes: [...], edges: [...]}.

    Raises ValueError on malformed output.
    Raises requests.HTTPError on API failures.
    """
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured.")

    model = model or settings.OPENROUTER_MODEL

    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": DECOMPOSITION_SYSTEM},
            {"role": "user", "content": build_user_prompt(goal_title, root_namespace, user_text)},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://axiom.local",
        "X-Title": "Axiom Cognitive Platform",
    }

    response = requests.post(OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=90)
    response.raise_for_status()

    raw_content: str = response.json()["choices"][0]["message"]["content"]

    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("OpenRouter returned non-JSON: %s", cleaned[:500])
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc

    if "nodes" not in data or "edges" not in data:
        raise ValueError("Response missing 'nodes' or 'edges' keys.")

    return data


def import_graph(goal, graph_data: dict[str, Any]) -> tuple[list, list]:
    """Persist decomposed graph data into the database.

    Returns (created_nodes, created_edges).
    """
    from .models import ConceptNode, Edge

    nodes_by_ns: dict[str, ConceptNode] = {}
    created_nodes = []

    for node_def in graph_data["nodes"]:
        ns = node_def["namespace"].strip().lower()
        node, _ = ConceptNode.objects.update_or_create(
            goal=goal,
            namespace=ns,
            defaults={
                "label": node_def.get("label", ns.split(".")[-1].replace("_", " ").title()),
                "summary": node_def.get("summary", ""),
                "cognitive_state": ConceptNode.CognitiveState.UNKNOWN,
            },
        )
        nodes_by_ns[ns] = node
        created_nodes.append(node)

    created_edges = []
    for edge_def in graph_data["edges"]:
        src_ns = edge_def["source"].strip().lower()
        tgt_ns = edge_def["target"].strip().lower()

        src = nodes_by_ns.get(src_ns)
        tgt = nodes_by_ns.get(tgt_ns)
        if not src or not tgt:
            logger.warning("Skipping edge %s → %s: node not found.", src_ns, tgt_ns)
            continue

        edge, _ = Edge.objects.update_or_create(
            goal=goal,
            source=src,
            target=tgt,
            defaults={
                "edge_type": Edge.EdgeType.REQUIRES,
                "weight": edge_def.get("weight", 1.0),
            },
        )
        created_edges.append(edge)

    return created_nodes, created_edges


def _assign_depths(goal) -> None:
    """BFS from root nodes (no inbound requires-edges) to set ConceptNode.depth."""
    import networkx as nx
    from .models import ConceptNode, Edge

    g = nx.DiGraph()
    nodes = list(goal.nodes.values_list("id", "namespace"))
    g.add_nodes_from(nodes)

    edges = list(goal.edges.values_list("source_id", "target_id"))
    g.add_edges_from(edges)

    roots = [n for n in g.nodes if g.in_degree(n) == 0]
    if not roots:
        return

    for root in roots:
        lengths = nx.single_source_shortest_path_length(g, root)
        for node_id, depth in lengths.items():
            ConceptNode.objects.filter(id=node_id).update(depth=depth)


def decompose_and_import(goal, user_text: str) -> tuple[list, list]:
    """Full pipeline: call LLM → import → assign depths."""
    graph_data = decompose_to_graph(goal.title, goal.root_namespace, user_text)
    nodes, edges = import_graph(goal, graph_data)
    _assign_depths(goal)
    return nodes, edges