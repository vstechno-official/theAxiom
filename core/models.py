# A Axiom entity ;)
from django.db import models
from django.core.validators import RegexValidator

CID_NAMESPACE_PATTERN = r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*){2,}$"
CIDValidator = RegexValidator(
    CID_NAMESPACE_PATTERN,
    "Namespace must be lowercase dot-separated (e.g. cisce.icse.chemistry.redox).",
)


class Goal(models.Model):
    title = models.CharField(max_length=256)
    description = models.TextField(blank=True)
    root_namespace = models.CharField(
        max_length=512,
        unique=True,
        validators=[CIDValidator],
        help_text="Root CID namespace (e.g. cisce.icse.chemistry).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ConceptNode(models.Model):
    class CognitiveState(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        BROKEN = "broken", "Broken"
        REPAIRED = "repaired", "Repaired"
        MASTERED = "mastered", "Mastered"

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="nodes")
    namespace = models.CharField(
        max_length=768,
        validators=[CIDValidator],
        help_text="Fully-qualified CID namespace.",
        db_index=True,
    )
    label = models.CharField(max_length=256)
    summary = models.TextField(blank=True, help_text="One-paragraph plain-English explanation.")
    cognitive_state = models.CharField(
        max_length=16,
        choices=CognitiveState.choices,
        default=CognitiveState.UNKNOWN,
        db_index=True,
    )
    depth = models.PositiveSmallIntegerField(
        default=0,
        help_text="Topological depth from the root goal node (0 = root).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["depth", "namespace"]
        constraints = [
            models.UniqueConstraint(fields=["goal", "namespace"], name="unique_goal_namespace"),
        ]

    def __str__(self):
        return f"{self.label} [{self.namespace}]"


class Edge(models.Model):
    class EdgeType(models.TextChoices):
        REQUIRES = "requires", "Requires"
        SUPPORTS = "supports", "Supports"

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="edges")
    source = models.ForeignKey(
        ConceptNode, on_delete=models.CASCADE, related_name="outbound_edges",
    )
    target = models.ForeignKey(
        ConceptNode, on_delete=models.CASCADE, related_name="inbound_edges",
    )
    edge_type = models.CharField(
        max_length=16,
        choices=EdgeType.choices,
        default=EdgeType.REQUIRES,
    )
    weight = models.FloatField(default=1.0, help_text="Dependency strength (0-1).")

    class Meta:
        ordering = ["source__depth"]
        constraints = [
            models.UniqueConstraint(
                fields=["goal", "source", "target"],
                name="unique_goal_edge",
            ),
        ]

    def __str__(self):
        return f"{self.source.namespace} → {self.target.namespace}"
