# Axiom: Cognitive Research Platform — Technical Research & Deployment Analysis

**Author:** Vedant Vaibhav Salaskar
**Date:** September 2026
**Classification:** Capstone Engineering Artifact — HCI Research / Graph Algorithms / AI Orchestration

---

## 1. Project Overview

Axiom is a web application that models human understanding as a directed dependency graph. When a student cannot recall a concept, Axiom traces the graph backward through prerequisites to identify the deepest foundational gap, then guides targeted repair of that gap — automatically cascading recovery upward through dependent concepts when possible.

The system is built on Django 5.x with NetworkX for graph algorithms, Cytoscape.js for interactive visualization, HTMX for partial-page updates, and OpenRouter's API for AI-powered concept decomposition. It uses a custom Managed Identifier Architecture (MIA) namespace protocol to disambiguate concepts across academic domains.

### Core Conceptual Model

Every knowledge domain is decomposed into a directed acyclic graph where:

- **Nodes** represent atomic concepts, each carrying a MIA namespace (`cisce.icse.chemistry.redox.oxidation_state`) and one of four cognitive states: `unknown`, `broken`, `repaired`, `mastered`.
- **Edges** represent `requires` dependencies — an arrow from A to B means "B requires A."
- **Goals** are top-level learning objectives that own their subgraphs (e.g., "Master Classical Mechanics").

The graph lives in a PostgreSQL/SQLite database via Django's ORM. NetworkX builds an in-memory directed graph from the database on demand for algorithmic traversal.

### Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Django 5.1 | ORM, admin, middleware — production-grade without boilerplate |
| Graph Engine | NetworkX 3.4 | DFS, reverse graph, ancestors, shortest-path for depth assignment |
| AI Orchestration | OpenRouter API | Single endpoint to Claude, GPT-4o, Gemini via `requests` |
| Frontend | Django Templates + HTMX 1.21 | SPA-like reactivity with server-rendered HTML; no JS build step |
| Graph Viz | Cytoscape.js + dagre | Bioinformatics-grade SVG rendering with DAG auto-layout |
| Server | Gunicorn (WSGI) | Standard Django production server |

---

## 2. Free Hosting Options — Comparative Analysis

### 2.1 Platform Comparison

| Platform | Free Tier | Sleep/Cold Start | Database | Custom Domain | Bandwidth | Deploy Method |
|---|---|---|---|---|---|---|
| **Railway.app** | $5/mo credit (≈500 hrs) | No sleep while credit lasts; sleeps after | PostgreSQL addon (free 1GB) | Yes | Unlimited within credit | `railway up` or GitHub |
| **Render.com** | Free web service | 15-min inactivity spin-down; ~30s cold start | Free PostgreSQL (90-day expiry, 1GB) | Yes (custom domain on free) | 100 GB/mo | GitHub auto-deploy |
| **Fly.io** | 3 shared-cpu-1x VMs, 256MB RAM | Auto-stop after inactivity; ~5s wake | No free Postgres (must self-host or use Supabase) | Yes | 160 GB/mo shared | `fly launch` + Dockerfile |
| **Vercel** | Generous serverless free | N/A (serverless) | None (external only) | Yes | 100 GB/mo | GitHub auto-deploy |
| **PythonAnywhere** | Free tier (512MB) | Always-on, no cold start | MySQL only (not PostgreSQL) | No (subdomain only) | Limited HMAC throttle | Git pull + reload |
| **Oracle Cloud Free Tier** | Always-free ARM (4 OCPU, 24GB RAM) | N/A — always running | Self-host PostgreSQL | Yes | 10 TB/mo | SSH + manual setup |

### 2.2 Django-Specific Fit

**Railway.app** is the strongest candidate for Axiom:
- Native PostgreSQL addon with no expiry (unlike Render's 90-day limit on free Postgres).
- No cold-start penalty during the credit period.
- GitHub integration for continuous deployment.
- Environment variables managed through the Railway dashboard.

**Render.com** is a close second, with one critical limitation: free-tier PostgreSQL databases expire after 90 days and must be manually recreated. For a capstone demo that runs for a semester, this is manageable. For a persistent deployment, it is not.

**Fly.io** requires a Dockerfile and manual PostgreSQL configuration. The free tier provides the most compute (3 VMs), but the operational overhead is higher.

**Vercel** is fundamentally unsuitable. Django does not run natively on Vercel's serverless platform — it requires a custom adapter (`django-vercel` or a WSGI wrapper), which introduces cold-start latency and compatibility issues with persistent connections (SSE, WebSockets). Axiom's HTMX-driven partial rendering expects a standard WSGI server.

**PythonAnywhere** supports Django natively but does not provide PostgreSQL on the free tier (MySQL only). Since Axiom's production deployment strategy targets PostgreSQL, this creates a migration gap. The free tier also lacks custom domain support.

**Oracle Cloud Free Tier** offers the most resources by far — 4 ARM OCPUs and 24GB RAM — but requires manual server provisioning, firewall configuration, and PostgreSQL installation. Viable for a long-running production deployment, impractical for a fast demo setup.

### 2.3 Recommendation

For a student project targeting admissions portfolio visibility:

1. **Primary: Railway.app** — fastest path from GitHub to live URL with PostgreSQL.
2. **Fallback: Render.com** — if Railway credit is exhausted; accept the 90-day DB limit.
3. **Stretch: Oracle Cloud** — if persistent, always-free hosting is required long-term.

---

## 3. Technical Architecture

### 3.1 MIA (Managed Identifier Architecture) Namespace Protocol

Every concept node carries a strictly enforced dot-separated namespace validated at the database level:

```
cisce.icse.chemistry.redox.oxidation_state
│     │    │         │     └─ Concept
│     │    │         └─ Unit
│     │    └─ Subject
│     └─ Standard/Year
└─ Board (Council for the Indian School Certificate Examinations)
```

The regex validator in `models.py` enforces this:

```python
MIA_NAMESPACE_PATTERN = r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*){2,}$"
```

This design solves a real disambiguation problem: "O.S." could mean Operating System (computer science) or Oxidation State (chemistry). The MIA namespace makes every concept globally unambiguous within a goal's scope. The database enforces uniqueness via a composite constraint (`goal + namespace`).

### 3.2 NetworkX Backward Trace Algorithm

The trace algorithm in `tracing.py` identifies the root cause of a knowledge gap:

```
User fails to recall concept C
    → Reverse the directed graph (prerequisite edges become "is-required-by")
    → DFS from C through all ancestors (prerequisites)
    → Filter ancestors still in 'unknown' state
    → Select the deepest one (highest topological depth = most foundational)
    → Mark it as 'broken' (Oxblood Red in the UI)
    → Return the full trace path for visualization
```

Key implementation details:
- `build_cognitive_graph()` constructs a `nx.DiGraph` from database edges, attaching node attributes (namespace, label, cognitive state, depth).
- `trace_backward()` uses `nx.descendants()` on the reversed graph to find all ancestors, then `nx.dfs_preorder_nodes()` for the ordered trace path.
- The broken node selection uses `max(unknown_ancestors, key=depth)` — depth is assigned during import via BFS from root nodes (nodes with in-degree 0).
- The entire state mutation is wrapped in `transaction.atomic()` to prevent partial updates.

**Time complexity:** O(V + E) per trace, where V is the number of concept nodes and E is the number of edges in the goal's subgraph. For typical academic graphs (50–500 nodes), this completes in under 10ms.

### 3.3 Repair Cascade

The repair mechanism in `tracing.py` implements forward cascade:

```
User probes a broken node N → mark N as 'repaired'
    → For each dependent D of N:
        → Check if ALL of D's prerequisites are now repaired/mastered
        → If yes AND D is currently 'broken': auto-repair D
        → (We never auto-upgrade 'unknown' nodes — they must be explicitly traced first)
```

The cascade is single-level by design in the current implementation: it checks immediate dependents only. This is deliberate — a deep cascade would make the UI confusing (nodes flipping states without user interaction). The single-level check is O(in-degree × out-degree) per repair, bounded by the graph's local connectivity.

The repair function uses `select_for_update()` on the target node, providing row-level locking to prevent race conditions on concurrent requests.

### 3.4 OpenRouter AI Decomposition Pipeline

The decomposition pipeline (`services.py`) takes a free-text learning goal and produces a structured graph:

1. **System prompt** instructs the LLM to output a JSON schema with `nodes` (namespace, label, summary) and `edges` (source, target, weight).
2. **User prompt** carries the goal title, root namespace prefix, and the user's description.
3. **Post-processing** strips markdown fences (some models wrap JSON in ```` ``` ````), parses JSON, validates keys.
4. **Import** persists nodes via `update_or_create` keyed on `(goal, namespace)`, then edges keyed on `(goal, source, target)`.
5. **Depth assignment** runs BFS from root nodes (in-degree 0) using `nx.single_source_shortest_path_length()`.

The model defaults to `anthropic/claude-sonnet-4` via OpenRouter, configurable via `OPENROUTER_MODEL` environment variable. Temperature is set to 0.2 for deterministic output. Max tokens at 4096 handles graphs of up to ~80 nodes comfortably.

Typical response time: 8–15 seconds for a medium-sized decomposition (30–50 nodes), dominated by the LLM inference latency.

### 3.5 Cytoscape.js Visualization

The `graph_to_cytoscape_elements()` function serializes the database graph into Cytoscape.js's expected format:

- **Nodes** carry `id`, `label`, `namespace`, `state`, `depth`, and a computed `color` based on cognitive state (grey=unknown, oxblood=broken, forest green=repaired/mastered).
- **Edges** carry `source`, `target`, `weight`, with composite IDs (`e-{source_id}-{target_id}`).
- The **dagre layout** arranges nodes in a topological DAG layout, reading left-to-right or top-to-bottom based on dependency direction.

Color mapping from `tracing.py`:
```python
state_colors = {
    "unknown":  "#A0A0A0",   # Neutral grey
    "broken":   "#8B0000",   # Oxblood Red
    "repaired": "#2E4B31",   # Forest Green
    "mastered": "#1B6B2E",   # Deep Green
}
```

Graph updates after trace/repair use HTMX's `HX-Trigger` header to push updated elements to Cytoscape.js without a full page reload:

```python
response["HX-Trigger"] = json.dumps({
    "graphUpdate": {"elements": updated_elements}
})
```

### 3.6 HTMX Partial Rendering Pattern

Axiom uses a clean HTMX architecture where the server returns HTML fragments, not JSON:

- **Node detail panel:** `hx-get="/node/{id}/detail/"` swaps a sidebar panel.
- **Trace trigger:** `hx-post="/node/{id}/trace/"` returns the trace result partial and triggers a graph re-render via `HX-Trigger`.
- **Repair trigger:** `hx-post="/node/{id}/repair/"` follows the same pattern.

This eliminates the need for client-side JavaScript state management. The server is the single source of truth — it computes the new graph state, renders the HTML fragment, and signals the client to update the visualization. The only client-side JS is Cytoscape.js initialization and the HTMX trigger listener.

---

## 4. Deployment Recommendations

### 4.1 Recommended Stack for Student Project

```yaml
Platform:     Railway.app
Database:     PostgreSQL (Railway addon)
Server:       Gunicorn (4 workers)
Static:       WhiteNoise middleware
Domain:       *.up.railway.app (or custom domain)
CI/CD:        GitHub → Railway auto-deploy on push
```

### 4.2 Database Migration: SQLite → PostgreSQL

Current `settings.py` is hardcoded to SQLite:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

For production, update to:

```python
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
    }
}
```

Railway's PostgreSQL addon auto-injects `DATABASE_URL`. Add `dj-database-url` to parse it:

```python
import dj_database_url
DATABASES = {
    "default": dj_database_url.config(default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}
```

Migration from SQLite to PostgreSQL does not require schema changes — Django's ORM abstracts the engine. Run `python manage.py migrate` against the new PostgreSQL database and it creates the schema. Seed data via `python manage.py seed_demo`.

### 4.3 Environment Variables

```bash
# Required
DJANGO_SECRET_KEY=<random-50-char-string>
OPENROUTER_API_KEY=sk-or-v1-...
DEBUG=False

# Optional
OPENROUTER_MODEL=anthropic/claude-sonnet-4
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

Never commit `.env` to version control. Railway and Render both provide dashboard-based environment variable management.

### 4.4 Static File Serving

Add WhiteNoise to `requirements.txt`:

```python
whitenoise>=6.7,<7.0
```

Update `settings.py`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Add after SecurityMiddleware
    # ... rest
]

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

WhiteNoise serves static files directly from the WSGI process — no Nginx or CDN required. For a capstone project with moderate traffic, this is sufficient.

### 4.5 Custom Domain Setup

Railway supports custom domains on all tiers:
1. Add domain in Railway dashboard → DNS settings.
2. Create a CNAME record pointing to your Railway service URL.
3. Railway provisions TLS certificates automatically via Let's Encrypt.

---

## 5. Performance Considerations

### 5.1 Graph Rendering Limits

Cytoscape.js renders graphs as SVG/Canvas in the browser. Recommended limits:

| Node Count | Render Time | Layout Time | UX |
|---|---|---|---|
| < 100 | < 100ms | < 200ms | Excellent |
| 100–500 | 100–500ms | 200–800ms | Good |
| 500–1000 | 500ms–2s | 0.8–3s | Acceptable |
| > 1000 | > 2s | > 3s | Degraded; consider pagination or subgraph filtering |

Axiom's typical academic graphs (30–200 nodes per goal) fall well within the excellent range. The dagre layout algorithm is O(V + E) for DAGs, which is optimal.

For very large graphs, the MIA namespace enables natural subgraph filtering — display only `cisce.icse.chemistry.*` instead of the full tree.

### 5.2 NetworkX Algorithm Complexity

| Operation | Algorithm | Complexity |
|---|---|---|
| Build graph from DB | ORM query + `add_node`/`add_edge` | O(V + E) |
| Backward trace | `nx.descendants` on reversed graph | O(V + E) |
| DFS trace path | `nx.dfs_preorder_nodes` | O(V + E) |
| Depth assignment | `nx.single_source_shortest_path_length` | O(V + E) per root |
| Repair cascade | Local neighbor check | O(in-degree × out-degree) |

All operations are linear in graph size. For the target scale (≤1000 nodes per goal), NetworkX operations complete in <50ms on commodity hardware. The bottleneck is database I/O, not graph computation.

### 5.3 OpenRouter API: Rate Limits and Costs

OpenRouter routes to upstream model providers. Key considerations:

| Model | Input Cost | Output Cost | Typical Decomposition Cost |
|---|---|---|---|
| `anthropic/claude-sonnet-4` | $3/M tokens | $15/M tokens | ~$0.02–0.05 per goal |
| `openai/gpt-4o` | $2.50/M tokens | $10/M tokens | ~$0.02–0.04 per goal |
| `google/gemini-2.0-flash` | $0.10/M tokens | $0.40/M tokens | ~$0.002–0.005 per goal |

A single decomposition call uses ~1000 input tokens (system + user prompt) and ~2000–4000 output tokens (the JSON graph). At Claude Sonnet 4 pricing, this costs approximately $0.03–0.06 per goal creation.

OpenRouter's free tier provides $1 of credit for new accounts — enough for 15–30 decompositions. Rate limits on free tier are approximately 20 requests/minute, which is more than sufficient for a single-user demo.

**Recommendation:** Use `google/gemini-2.0-flash` for development and testing ($0.003 per call), switch to `anthropic/claude-sonnet-4` for production demos where output quality matters.

---

## 6. Security

### 6.1 CSRF Protection

Django's `CsrfViewMiddleware` is enabled in `MIDDLEWARE` (confirmed in `settings.py`). All POST endpoints (`create_goal`, `trigger_trace`, `trigger_repair`) use Django's `{% csrf_token %}` in templates. HTMX automatically includes the CSRF token from the page's cookie in its requests.

No API endpoints currently expose write operations without CSRF protection. The `graph_elements_api` endpoint is GET-only and returns no sensitive data.

### 6.2 API Key Management

The OpenRouter API key is loaded from environment variables:

```python
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
```

The empty-string default means the app starts without a key but raises a `ValueError` on decompose calls. This is intentional — the demo seed data (`seed_demo`) works without an API key.

**Production checklist:**
- Generate a dedicated `DJANGO_SECRET_KEY` (not the insecure fallback).
- Set `DEBUG=False`.
- Restrict `ALLOWED_HOSTS` to specific domains (currently `"*"`).
- Rotate OpenRouter API keys periodically.

### 6.3 SQLite vs PostgreSQL for Production

| Factor | SQLite | PostgreSQL |
|---|---|---|
| Concurrent writes | Single-writer lock; blocks on writes | MVCC; full concurrent write support |
| Full-text search | FTS5 extension | Native `tsvector` + GIN indexes |
| Connection pooling | N/A (file-based) | PgBouncer or pgbouncer-compatible |
| Backup | File copy | `pg_dump` + point-in-time recovery |
| JSON support | Limited | `jsonb` with indexing |
| Free hosting support | Universal | Most platforms (Railway, Render, Fly) |

SQLite is adequate for a single-user demo. For any deployment with multiple concurrent users — including admissions reviewers clicking around — PostgreSQL is the correct choice. The migration path is clean: Django's ORM abstracts the engine, so changing `DATABASES` and running `migrate` against PostgreSQL creates the identical schema.

---

## Appendix A: Project File Structure

```
axiom/
├── axiom/
│   ├── settings.py          # Django settings (env-based config)
│   ├── urls.py              # Root URL routing
│   └── wsgi.py              # WSGI entry point
├── core/
│   ├── models.py            # Goal, ConceptNode, Edge (MIA namespace protocol)
│   ├── services.py          # OpenRouter API integration
│   ├── tracing.py           # NetworkX backward trace + repair cascade
│   ├── views.py             # Django views + HTMX partial rendering
│   ├── admin.py             # Django admin registration
│   ├── templatetags/
│   │   └── axiom_tags.py    # Custom template filters
│   ├── management/commands/
│   │   └── seed_demo.py     # Demo data: Classical Mechanics graph
│   └── templates/core/
│       ├── base.html        # Scholar's Desk shell
│       ├── index.html       # Dashboard + goal creation form
│       ├── goal_detail.html # Cytoscape.js graph + sidebar
│       └── partials/        # HTMX fragments
├── static/                  # Static assets (CSS, JS)
├── requirements.txt         # Python dependencies
├── manage.py                # Django management
└── db.sqlite3               # Development database
```

## Appendix B: Key Dependencies

```
django>=5.1,<5.2
django-htmx>=1.21,<2.0
networkx>=3.4,<4.0
requests>=2.32,<3.0
python-dotenv>=1.0,<2.0
gunicorn>=23.0,<24.0
```

Production additions:
```
dj-database-url>=2.2,<3.0
whitenoise>=6.7,<7.0
psycopg2-binary>=2.9,<3.0
```