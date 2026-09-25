from django.contrib import admin
from .models import ConceptNode, Edge, Goal


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("title", "root_namespace", "created_at")
    search_fields = ("title", "root_namespace")


@admin.register(ConceptNode)
class ConceptNodeAdmin(admin.ModelAdmin):
    list_display = ("label", "namespace", "cognitive_state", "depth", "goal")
    list_filter = ("cognitive_state", "goal")
    search_fields = ("label", "namespace")


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("source", "target", "edge_type", "weight", "goal")