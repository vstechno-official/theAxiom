# A Axiom entity ;)
from __future__ import annotations

import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

FREE_MODELS = [
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "deepseek/deepseek-r1-0528:free",
]

CHAT_SYSTEM = """\
You are Axiom — a cognitive research assistant embedded inside a dependency graph visualization tool.

Your job is to help the user understand a subject by:
1. Explaining concepts clearly at their level
2. Manipulating the knowledge graph based on what they say
3. Asking probing questions to assess their understanding
4. Identifying gaps in their prerequisite knowledge

When the user says something that implies graph changes, return structured actions.

You MUST always return valid JSON with this exact schema:
{
  "reply": "your conversational response to the user (markdown allowed)",
  "actions": [
    {"action": "create_node", "namespace": "x.y.z", "label": "Name", "summary": "one paragraph"},
    {"action": "remove_node", "namespace": "x.y.z"},
    {"action": "create_edge", "source": "x.y.z", "target": "a.b.c", "weight": 0.8},
    {"action": "remove_edge", "source": "x.y.z", "target": "a.b.c"},
    {"action": "mark_broken", "namespace": "x.y.z"},
    {"action": "mark_repaired", "namespace": "x.y.z"}
  ]
}

RULES:
- The reply field is ALWAYS required. Actions array can be empty if no graph changes needed.
- Namespaces must be lowercase dot-separated (e.g. physics.mechanics.newtons_laws).
- When the user says they don't understand something, add a mark_broken action for that node.
- When the user explains something correctly, add a mark_repaired action.
- When the user asks to add a concept, create it with a create_node action.
- When the user says two concepts are related, create_edge between them.
- Always explain WHY you're making graph changes.
- Be direct. Be encouraging but not fake. Talk like a brilliant tutor, not a customer service bot.
- Use the user's profile info to tailor explanations to their level.
- If the user asks about a concept, explain it and check if prerequisites exist in the graph.
"""


def call_openrouter(messages: list[dict], model: str | None = None, api_key: str | None = None, temperature: float = 0.3, max_tokens: int = 2048) -> dict:
    api_key = api_key or settings.OPENROUTER_API_KEY
    if not api_key:
        return {
            "reply": "no openrouter api key found. click the gear icon (bottom-right) and paste your key. get a free one at openrouter.ai/keys",
            "actions": [],
        }

    model = model or settings.OPENROUTER_MODEL
    for fallback in [model] + FREE_MODELS:
        try:
            payload = {
                "model": fallback,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": messages,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://axiom.local",
                "X-Title": "Axiom Cognitive Platform",
            }
            resp = requests.post(OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return _parse_chat_response(raw)
        except Exception as exc:
            logger.warning("Model %s failed: %s", fallback, exc)
            continue

    return {"reply": "All models failed. Check your API key and try again.", "actions": []}


def _parse_chat_response(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[:-1])
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"reply": cleaned, "actions": []}

    if "reply" not in data:
        return {"reply": cleaned, "actions": []}

    return data


def build_chat_messages(goal, user_profile: dict, history: list[dict], user_message: str) -> list[dict]:
    context_parts = []
    if user_profile:
        context_parts.append(f"USER PROFILE: {json.dumps(user_profile)}")

    nodes = list(goal.nodes.values("namespace", "label", "cognitive_state", "depth"))
    edges = list(goal.edges.values("source__namespace", "target__namespace", "weight"))
    context_parts.append(f"CURRENT GRAPH NODES: {json.dumps(nodes)}")
    context_parts.append(f"CURRENT GRAPH EDGES: {json.dumps(edges)}")

    system = CHAT_SYSTEM + "\n\n" + "\n".join(context_parts)

    messages = [{"role": "system", "content": system}]
    for msg in history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    return messages


def execute_chat_actions(goal, actions: list[dict]) -> list[str]:
    from .models import ConceptNode, Edge

    results = []
    for act in actions:
        action = act.get("action")
        ns = act.get("namespace", "").strip().lower()

        if action == "create_node" and ns:
            node, created = ConceptNode.objects.get_or_create(
                goal=goal, namespace=ns,
                defaults={
                    "label": act.get("label", ns.split(".")[-1].replace("_", " ").title()),
                    "summary": act.get("summary", ""),
                },
            )
            results.append(f"created node: {node.label}" if created else f"node exists: {node.label}")

        elif action == "remove_node" and ns:
            deleted, _ = ConceptNode.objects.filter(goal=goal, namespace=ns).delete()
            results.append(f"removed node: {ns}" if deleted else f"node not found: {ns}")

        elif action == "create_edge":
            src_ns = act.get("source", "").strip().lower()
            tgt_ns = act.get("target", "").strip().lower()
            src = ConceptNode.objects.filter(goal=goal, namespace=src_ns).first()
            tgt = ConceptNode.objects.filter(goal=goal, namespace=tgt_ns).first()
            if src and tgt:
                Edge.objects.get_or_create(goal=goal, source=src, target=tgt, defaults={"weight": act.get("weight", 0.8)})
                results.append(f"edge: {src_ns} -> {tgt_ns}")
            else:
                results.append(f"edge failed: node not found")

        elif action == "remove_edge":
            src_ns = act.get("source", "").strip().lower()
            tgt_ns = act.get("target", "").strip().lower()
            deleted, _ = Edge.objects.filter(
                goal=goal, source__namespace=src_ns, target__namespace=tgt_ns
            ).delete()
            results.append(f"removed edge: {src_ns} -> {tgt_ns}" if deleted else "edge not found")

        elif action == "mark_broken" and ns:
            updated = ConceptNode.objects.filter(goal=goal, namespace=ns).update(cognitive_state="broken")
            results.append(f"broken: {ns}" if updated else f"node not found: {ns}")

        elif action == "mark_repaired" and ns:
            updated = ConceptNode.objects.filter(goal=goal, namespace=ns).update(cognitive_state="repaired")
            results.append(f"repaired: {ns}" if updated else f"node not found: {ns}")

    return results
