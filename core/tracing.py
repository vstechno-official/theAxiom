"""NetworkX-powered backward dependency tracing for Axiom's cognitive graph.

The Trace Protocol:
    1. User fails to recall a concept C.
    2. Walk backward through all 'requires' edges to find the deepest
       foundational prerequisite that is still in 'unknown' or 'broken' state.
    3. Mark that leaf prerequisite as 'broken' (Oxblood Red).
    4. Return the full trace path for UI rendering.

The Repair Protocol:
    1. User successfully probes a broken node.
    2. Mark it as 'repaired' (Forest Green).
    3. Check if all its prerequisites are now repaired/mastered.
    4. If yes, cascade 'repaired' up to dependents that were waiting on it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx
from django.db import transaction

from .models import ConceptNode, Edge, Goal

logger = logging.getLogger(__name__)


@dataclass
class TraceResult:
    origin: ConceptNode
    broken_node: ConceptNode
    trace_path: list[ConceptNode] = field(default_factory=list)
    all_ancestors: list[ConceptNode] = field(default_factory=list)


def build_cognitive_graph(goal: Goal) -> nx.DiGraph:
    """Construct a directed graph from the goal's edges.

    Node attributes are pulled from ConceptNode rows so the graph
    is self-contained for algorithmic traversal.
    """
    g = nx.DiGraph()

    for node in goal.nodes.all():
        g.add_node(
            node.id,
            namespace=node.namespace,
            label=node.label,
            cognitive_state=node.cognitive_state,
            depth=node.depth,
        )

    for edge in goal.edges.select_related("source", "target"):
        g.add_edge(
            edge.source_id,
            edge.target_id,
            weight=edge.weight,
            edge_type=edge.edge_type,
        )

    return g


def trace_backward(goal: Goal, failed_node_id: int) -> TraceResult:
    """Execute the backward trace when a user fails to recall `failed_node_id`.

    Algorithm:
        1. Build the cognitive graph for this goal.
        2. Reverse the graph so 'requires' edges become 'is-required-by' edges.
        3. DFS from the failed node to find all ancestors (prerequisites).
        4. Among ancestors still in 'unknown' state, find the deepest one
           (highest depth value = most foundational).
        5. If no unknown ancestors exist, mark the failed node itself as broken.
        6. Otherwise mark the deepest unknown ancestor as broken.

    Returns a TraceResult with the broken node and the path taken.
    """
    g = build_cognitive_graph(goal)
    reversed_g = g.reverse()

    if failed_node_id not in reversed_g:
        raise ValueError(f"Node {failed_node_id} not in graph for goal {goal.id}")

    ancestors: list[int] = list(nx.descendants(reversed_g, failed_node_id)) if reversed_g.out_degree(failed_node_id) > 0 else []
    ancestors.append(failed_node_id)

    trace_path_ids = []
    if reversed_g.out_degree(failed_node_id) > 0:
        dfs_tree = nx.dfs_tree(reversed_g, source=failed_node_id)
        trace_path_ids = list(nx.dfs_preorder_nodes(dfs_tree, failed_node_id))

    unknown_ancestors = [
        nid for nid in ancestors
        if g.nodes[nid].get("cognitive_state") in (
            ConceptNode.CognitiveState.UNKNOWN,
            ConceptNode.CognitiveState.BROKEN,
        )
    ]

    broken_candidates = [
        nid for nid in unknown_ancestors
        if g.nodes[nid].get("cognitive_state") == ConceptNode.CognitiveState.UNKNOWN
    ]

    if not broken_candidates:
        target_id = failed_node_id
    else:
        target_id = max(broken_candidates, key=lambda nid: g.nodes[nid].get("depth", 0))

    with transaction.atomic():
        ConceptNode.objects.filter(id=target_id).update(
            cognitive_state=ConceptNode.CognitiveState.BROKEN
        )

    origin = ConceptNode.objects.get(id=failed_node_id)
    broken_node = ConceptNode.objects.get(id=target_id)
    trace_path = list(ConceptNode.objects.filter(id__in=trace_path_ids))
    all_ancestors = list(ConceptNode.objects.filter(id__in=ancestors))

    return TraceResult(
        origin=origin,
        broken_node=broken_node,
        trace_path=trace_path,
        all_ancestors=all_ancestors,
    )


def repair_node(goal: Goal, node_id: int) -> dict:
    """Mark a broken node as repaired and cascade if possible.

    Cascade logic:
        If all prerequisites of a dependent are now repaired/mastered,
        that dependent becomes eligible for auto-repair (but only if
        it was previously broken — we never auto-upgrade unknown nodes).

    Returns a dict with the repaired node and any cascaded repairs.
    """
    g = build_cognitive_graph(goal)

    with transaction.atomic():
        node = ConceptNode.objects.select_for_update().get(id=node_id, goal=goal)
        if node.cognitive_state != ConceptNode.CognitiveState.BROKEN:
            return {"node": node, "cascaded": []}

        node.cognitive_state = ConceptNode.CognitiveState.REPAIRED
        node.save(update_fields=["cognitive_state"])

        cascaded = []
        dependents = list(g.successors(node_id))

        for dep_id in dependents:
            prereq_states = [
                g.nodes[pid]["cognitive_state"]
                for pid in g.predecessors(dep_id)
            ]

            all_good = all(
                s in (ConceptNode.CognitiveState.REPAIRED, ConceptNode.CognitiveState.MASTERED)
                for s in prereq_states
            )

            if all_good:
                dep_node = ConceptNode.objects.filter(
                    id=dep_id,
                    cognitive_state=ConceptNode.CognitiveState.BROKEN,
                ).first()
                if dep_node:
                    dep_node.cognitive_state = ConceptNode.CognitiveState.REPAIRED
                    dep_node.save(update_fields=["cognitive_state"])
                    cascaded.append(dep_node)

    return {"node": node, "cascaded": cascaded}


def graph_to_cytoscape_elements(goal: Goal) -> list[dict]:
    """Serialize the goal's graph into Cytoscape.js element format."""
    elements = []

    state_colors = {
        ConceptNode.CognitiveState.UNKNOWN: "#666666",
        ConceptNode.CognitiveState.BROKEN: "#b33a3a",
        ConceptNode.CognitiveState.REPAIRED: "#3a7a4a",
        ConceptNode.CognitiveState.MASTERED: "#2a9d4a",
    }

    for node in goal.nodes.all():
        elements.append({
            "data": {
                "id": str(node.id),
                "label": node.label,
                "namespace": node.namespace,
                "state": node.cognitive_state,
                "depth": node.depth,
                "color": state_colors.get(node.cognitive_state, "#A0A0A0"),
            }
        })

    for edge in goal.edges.select_related("source", "target"):
        elements.append({
            "data": {
                "id": f"e-{edge.source_id}-{edge.target_id}",
                "source": str(edge.source_id),
                "target": str(edge.target_id),
                "weight": edge.weight,
            }
        })

    return elements


def get_node_detail_context(node_id: int) -> dict:
    """Return a rich context dict for rendering a node detail panel."""
    node = ConceptNode.objects.select_related("goal").get(id=node_id)
    prerequisites = ConceptNode.objects.filter(
        outbound_edges__target=node
    ).distinct()
    dependents = ConceptNode.objects.filter(
        inbound_edges__source=node
    ).distinct()

    return {
        "node": node,
        "prerequisites": prerequisites,
        "dependents": dependents,
    }