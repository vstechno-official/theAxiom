from __future__ import annotations

import json
import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .chat_services import build_chat_messages, call_openrouter, execute_chat_actions
from .models import Goal
from .tracing import graph_to_cytoscape_elements

logger = logging.getLogger(__name__)

ONBOARDING_QUESTIONS = [
    "what's your name?",
    "how old are you?",
    "what are you studying? (school, college, self-learning?)",
    "what subjects are you strongest in?",
    "how would you explain your learning style? (visual, reading, hands-on, examples?)",
]


@require_POST
def chat_message(request, goal_id: int):
    goal = get_object_or_404(Goal, id=goal_id)
    user_msg = request.POST.get("message", "").strip()
    if not user_msg:
        return HttpResponse("")

    session_key = f"axiom_chat_{goal_id}"
    profile_key = f"axiom_profile_{goal_id}"

    history = request.session.get(session_key, [])
    user_profile = request.session.get(profile_key, {})

    if not history and not user_profile:
        request.session[profile_key] = {"onboarding_complete": False, "step": 0}
        user_profile = request.session[profile_key]

    if not user_profile.get("onboarding_complete"):
        step = user_profile.get("step", 0)
        key_map = ["name", "age", "education", "strengths", "learning_style"]
        if step < len(key_map):
            user_profile[key_map[step]] = user_msg
            user_profile["step"] = step + 1
            if step + 1 >= len(key_map):
                user_profile["onboarding_complete"] = True
                request.session[profile_key] = user_profile
                request.session.modified = True

                history.append({"role": "user", "content": user_msg})
                welcome = (
                    f"got it. so you're {user_profile.get('name', '')}, "
                    f"{user_profile.get('age', '')}, studying {user_profile.get('education', '')}. "
                    f"strong in {user_profile.get('strengths', '')}, learns best through {user_profile.get('learning_style', '')}. "
                    f"i'll tailor my explanations to that.\n\n"
                    f"you can:\n"
                    f"- ask me to explain any concept\n"
                    f"- say 'add [concept]' to add a node\n"
                    f"- say 'I don't understand [x]' to mark it broken\n"
                    f"- say 'connect [x] to [y]' to create edges\n"
                    f"- say 'remove [x]' to delete a node\n\n"
                    f"what do you want to understand?"
                )
                history.append({"role": "assistant", "content": welcome})
                request.session[session_key] = history
                request.session.modified = True

                return _render_chat_response(request, goal, welcome, [], user_profile, history)

            question = ONBOARDING_QUESTIONS[step + 1] if step + 1 < len(ONBOARDING_QUESTIONS) else ""
            request.session[profile_key] = user_profile
            request.session.modified = True

            history.append({"role": "user", "content": user_msg})
            history.append({"role": "assistant", "content": question})
            request.session[session_key] = history
            request.session.modified = True

            return _render_chat_response(request, goal, question, [], user_profile, history)

    history.append({"role": "user", "content": user_msg})

    messages = build_chat_messages(goal, user_profile, history, user_msg)
    ai_response = call_openrouter(messages)

    reply = ai_response.get("reply", "something went wrong.")
    actions = ai_response.get("actions", [])

    action_results = execute_chat_actions(goal, actions) if actions else []

    history.append({"role": "assistant", "content": reply})
    if len(history) > 100:
        history = history[-60:]
    request.session[session_key] = history
    request.session.modified = True

    return _render_chat_response(request, goal, reply, action_results, user_profile, history)


def _render_chat_response(request, goal, reply, action_results, user_profile, history):
    elements = graph_to_cytoscape_elements(goal)
    nodes = goal.nodes.order_by("depth", "namespace")

    from django.template.loader import render_to_string
    msg_html = render_to_string("core/partials/chat_msg.html", {"reply": reply, "actions": action_results})

    response = HttpResponse(msg_html)
    if action_results:
        response["HX-Trigger"] = json.dumps({
            "graphUpdate": {"elements": elements}
        })
    return response


@require_POST
def chat_reset(request, goal_id: int):
    request.session.pop(f"axiom_chat_{goal_id}", None)
    request.session.pop(f"axiom_profile_{goal_id}", None)
    request.session.modified = True
    return HttpResponse(
        '<div class="chat-msg chat-msg--ai">session cleared. say hi to start fresh.</div>'
    )