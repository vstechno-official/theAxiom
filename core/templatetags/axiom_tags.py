from django import template

register = template.Library()


@register.filter
def state_color(state):
    colors = {
        "unknown": "#666666",
        "broken": "#b33a3a",
        "repaired": "#3a7a4a",
        "mastered": "#2a9d4a",
    }
    return colors.get(state, "#666666")


@register.filter
def state_icon(state):
    icons = {
        "unknown": "○",
        "broken": "✗",
        "repaired": "◐",
        "mastered": "●",
    }
    return icons.get(state, "○")