from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("goal/create/", views.create_goal, name="create_goal"),
    path("goal/<int:goal_id>/", views.goal_detail, name="goal_detail"),
    path("goal/<int:goal_id>/elements/", views.graph_elements_api, name="graph_elements_api"),
    path("node/<int:node_id>/", views.node_detail, name="node_detail"),
    path("node/<int:node_id>/trace/", views.trigger_trace, name="trigger_trace"),
    path("node/<int:node_id>/repair/", views.trigger_repair, name="trigger_repair"),
]