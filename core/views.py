# A Axiom entity ;)
from __future__ import annotations

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django_htmx.http import reswap, retarget

from .models import ConceptNode, Goal
from .services import decompose_and_import
from .tracing import (
    build_cognitive_graph,
    get_node_detail_context,
    graph_to_cytoscape_elements,
    repair_node,
    trace_backward,
)

logger = logging.getLogger(__name__)


def index(request):
    goals = Goal.objects.all()
    return render(request, "core/index.html", {"goals": goals})


@require_POST
def create_goal(request):
    title = request.POST.get("title", "").strip()
    description = request.POST.get("description", "").strip()
    root_namespace = request.POST.get("root_namespace", "").strip()
    user_text = request.POST.get("user_text", "").strip()

    if not title or not root_namespace or not user_text:
        return HttpResponse(
            '<div class="form-error">Title, namespace, and description are required.</div>',
            status=400,
        )

    goal = Goal.objects.create(
        title=title,
        description=description,
        root_namespace=root_namespace,
    )

    api_key = request.headers.get("X-Axiom-Api-Key", "").strip() or None

    try:
        nodes, edges = decompose_and_import(goal, user_text, api_key=api_key)
    except Exception as exc:
        goal.delete()
        logger.exception("Decomposition failed for goal %s", title)
        return HttpResponse(
            f'<div class="form-error">AI decomposition failed: {exc}</div>',
            status=500,
        )

    return redirect("goal_detail", goal_id=goal.id)


@require_GET
def goal_detail(request, goal_id: int):
    goal = get_object_or_404(Goal, id=goal_id)
    elements = graph_to_cytoscape_elements(goal)
    nodes = goal.nodes.order_by("depth", "namespace")
    stats = {
        "total": nodes.count(),
        "unknown": nodes.filter(cognitive_state=ConceptNode.CognitiveState.UNKNOWN).count(),
        "broken": nodes.filter(cognitive_state=ConceptNode.CognitiveState.BROKEN).count(),
        "repaired": nodes.filter(cognitive_state=ConceptNode.CognitiveState.REPAIRED).count(),
        "mastered": nodes.filter(cognitive_state=ConceptNode.CognitiveState.MASTERED).count(),
    }
    return render(request, "core/goal_detail.html", {
        "goal": goal,
        "elements_json": json.dumps(elements),
        "nodes": nodes,
        "stats": stats,
    })


@require_GET
def node_detail(request, node_id: int):
    ctx = get_node_detail_context(node_id)
    return render(request, "core/partials/node_detail.html", ctx)


@require_POST
def trigger_trace(request, node_id: int):
    node = get_object_or_404(ConceptNode, id=node_id)
    result = trace_backward(node.goal_id, node_id)

    updated_elements = graph_to_cytoscape_elements(node.goal)
    node.refresh_from_db()

    ctx = get_node_detail_context(node_id)
    ctx["trace_result"] = result

    response = render(request, "core/partials/trace_result.html", ctx)
    response["HX-Trigger"] = json.dumps({
        "graphUpdate": {"elements": updated_elements}
    })
    return response


@require_POST
def trigger_repair(request, node_id: int):
    node = get_object_or_404(ConceptNode, id=node_id)
    result = repair_node(node.goal_id, node_id)

    updated_elements = graph_to_cytoscape_elements(node.goal)
    node.refresh_from_db()

    ctx = get_node_detail_context(node_id)
    ctx["repair_result"] = result

    response = render(request, "core/partials/repair_result.html", ctx)
    response["HX-Trigger"] = json.dumps({
        "graphUpdate": {"elements": updated_elements}
    })
    return response


@require_GET
def graph_elements_api(request, goal_id: int):
    goal = get_object_or_404(Goal, id=goal_id)
    elements = graph_to_cytoscape_elements(goal)
    return JsonResponse({"elements": elements})
