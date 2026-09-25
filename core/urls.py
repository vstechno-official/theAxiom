# A Axiom entity ;)
from django.urls import path

from . import chat_views, views

urlpatterns = [
    path("", views.index, name="index"),
    path("goal/create/", views.create_goal, name="create_goal"),
    path("goal/<int:goal_id>/", views.goal_detail, name="goal_detail"),
    path("goal/<int:goal_id>/elements/", views.graph_elements_api, name="graph_elements_api"),
    path("goal/<int:goal_id>/chat/", chat_views.chat_message, name="chat_message"),
    path("goal/<int:goal_id>/chat/reset/", chat_views.chat_reset, name="chat_reset"),
    path("node/<int:node_id>/", views.node_detail, name="node_detail"),
    path("node/<int:node_id>/trace/", views.trigger_trace, name="trigger_trace"),
    path("node/<int:node_id>/repair/", views.trigger_repair, name="trigger_repair"),
]
