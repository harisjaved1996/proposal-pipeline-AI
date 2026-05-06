---
name: proposal-pipeline-ui-designer
description: Designs and generates Django templates for the Proposal Pipeline AI — a multi-agent consulting tool built on Django 6 with AdminLTE3, Bootstrap 4, and vanilla JS. Creates professional, data-dense UI for pipeline runs, human-in-the-loop review gates, iteration history, and eval results. Use this skill whenever the user asks to design, build, create, redesign, improve, or style any page, component, or template.
disable-model-invocation: false
---

# Proposal Pipeline UI Designer

You are building frontend UI for the **Proposal Pipeline AI**, a Django 6 multi-agent tool used by internal consulting staff. Output professional Django templates, plain CSS, and vanilla JavaScript that follow AdminLTE3's dark sidebar + white content layout pattern.

## Stack Context

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Backend** | Django 6.0.4 | Python 3.x, MVT pattern |
| **Templates** | Django `.html` files | Always extend a shared base layout |
| **Markup** | HTML5 | Semantic tags throughout |
| **Styles** | Plain CSS 3 | `static/css/` — no Tailwind, no SCSS |
| **Scripts** | Vanilla JavaScript (ES6+) | `static/js/` — no jQuery (except what AdminLTE3 requires), no React/Vue |
| **UI Framework** | AdminLTE3 + Bootstrap 4 | via `django-adminlte3` and `django-bootstrap4` |
| **Icons** | Font Awesome 5 | `<i class="fas fa-icon-name"></i>` |
| **Font** | Source Sans Pro (AdminLTE3 default) | 400 body, 600 headings |

## Django Template Conventions

```html
{% extends "adminlte/base.html" %}
{% load static %}

{% block title %}Page Title{% endblock %}

{% block content_header %}
<div class="container-fluid">
  <h1>Page Title</h1>
</div>
{% endblock %}

{% block content %}
<div class="container-fluid">
  <!-- page content here -->
</div>
{% endblock %}
```

- Always extend the shared AdminLTE3 base — never standalone HTML files
- Use `{% url 'namespace:name' %}` for all links — never hardcode URLs
- Use `{% static 'css/file.css' %}` for all asset paths
- Escape all user-supplied output: `{{ variable|escape }}` or use Django's auto-escaping
- CSRF token in every form: `{% csrf_token %}`
- Use `{{ form.as_p }}` or `crispy_forms` for Django form rendering

## Pre-Design Checklist

Before generating new UI, always:

1. **Check Existing Templates**
   - Look in `templates/` for established layout patterns and component reuse
   - Identify established block names in the base template

2. **Check Static Assets**
   - Look in `static/css/` for existing custom classes (`.pp-` prefix)
   - Look in `static/js/` for existing utilities

3. **Understand the Data Shape**
   - Know the Pydantic/Django model being displayed (ClientMatrix, ProposalDocument, ReviewResult, etc.)
   - Status fields (`confidence`, `recommendation`) need visual distinction

4. **Identify the User Flow**
   - Is this a read view (matrix display, proposal view) or an action view (human gate, feedback form)?

## Design Language

### Color Palette (extending AdminLTE3 defaults)

- **Sidebar:** `#343a40` (dark gray) — AdminLTE3 default `sidebar-dark-primary`
- **Primary:** `#007bff` (blue) — actions, links, active nav
- **Success:** `#28a745` (green) — `high` confidence, approved status
- **Warning:** `#ffc107` (amber) — `medium` confidence, revise status
- **Danger:** `#dc3545` (red) — `contradicted` confidence, errors, escalate status
- **Secondary:** `#6c757d` (gray) — `low` confidence, muted info
- **Info:** `#17a2b8` (teal) — informational callouts, cost/token stats
- **Surface:** `#ffffff` (white) — cards, content area
- **Page BG:** `#f4f6f9` (light gray) — AdminLTE3 default body background

### Confidence Badge Mapping

Always render confidence levels as Bootstrap badges:

```html
{% if item.confidence == "high" %}
  <span class="badge badge-success">High</span>
{% elif item.confidence == "medium" %}
  <span class="badge badge-warning">Medium</span>
{% elif item.confidence == "low" %}
  <span class="badge badge-secondary">Low</span>
{% elif item.confidence == "contradicted" %}
  <span class="badge badge-danger">Contradicted</span>
{% endif %}
```

### Recommendation Badge Mapping

```html
{% if review.recommendation == "approve" %}
  <span class="badge badge-success badge-lg">Approve</span>
{% elif review.recommendation == "revise" %}
  <span class="badge badge-warning badge-lg">Revise</span>
{% elif review.recommendation == "escalate_to_human" %}
  <span class="badge badge-danger badge-lg">Escalate</span>
{% endif %}
```

## Key Page Patterns

### Pipeline Run Form (start a run)
- Card with two file upload areas (or text pasted): intake doc + transcript selector
- Transcript A / B radio or dropdown
- Submit button triggers the pipeline (POST → redirect to run detail)

### Run Detail / Iteration View
- Left: current proposal rendered as markdown (use a `<pre>` or a markdown-to-HTML filter)
- Right: Review Agent output — issues list (card per issue with severity badge), recommendation badge, translated feedback block
- Bottom: Human feedback textarea + Approve / Request Revision buttons
- Iteration breadcrumbs at top showing `v1 → v2 → v3`

### 4×4 Client Matrix Table
- Render as a responsive HTML table — rows are dimensions, columns are matrix fields
- Each cell contains a list of items; each item shows: statement, confidence badge, source quote in `<small class="text-muted">`
- `contradicted` items get a `table-danger` row highlight and show `contradiction_note` in a callout below the statement
- Wrap in `<div class="table-responsive">`

### Observability / Cost Log
- AdminLTE3 `info-box` components for: total cost, total tokens, total iterations, total latency
- Timeline component (`<div class="timeline">`) for per-call log entries
- Each log entry: agent name, model, input/output tokens, cost, latency

### Eval Results
- Two cards side by side: Matrix Contradiction Recall + Loop Regression
- Each card shows: pass/fail badge, score %, detail table of test cases

## CSS Class Reference (`.pp-` prefix for custom classes)

| Class | Purpose |
|-------|---------|
| `.pp-matrix-table` | The 4×4 client matrix table |
| `.pp-matrix-cell` | Individual matrix cell wrapper |
| `.pp-contradicted-row` | Row highlight for contradicted items |
| `.pp-proposal-body` | Markdown proposal rendered area |
| `.pp-feedback-form` | Human feedback textarea + action buttons |
| `.pp-issue-card` | Single review issue card |
| `.pp-cost-stat` | Token/cost stat display |
| `.pp-iteration-nav` | Breadcrumb-style iteration navigator |
| `.pp-source-quote` | Source excerpt styling (italic, muted) |
| `.pp-contradiction-note` | Contradiction explanation callout |

## AdminLTE3 Component Quick Reference

```html
<!-- Info Box (stats) -->
<div class="info-box">
  <span class="info-box-icon bg-info"><i class="fas fa-dollar-sign"></i></span>
  <div class="info-box-content">
    <span class="info-box-text">Total Cost</span>
    <span class="info-box-number">$0.042</span>
  </div>
</div>

<!-- Card -->
<div class="card card-primary">
  <div class="card-header"><h3 class="card-title">Title</h3></div>
  <div class="card-body">...</div>
  <div class="card-footer">...</div>
</div>

<!-- Alert -->
<div class="alert alert-warning alert-dismissible">
  <button type="button" class="close" data-dismiss="alert">&times;</button>
  <i class="icon fas fa-exclamation-triangle"></i> Message
</div>

<!-- Timeline entry -->
<div class="time-label"><span class="bg-primary">Agent Call</span></div>
<div><i class="fas fa-robot bg-blue"></i>
  <div class="timeline-item">
    <span class="time"><i class="fas fa-clock"></i> 1.2s | 340 tokens | $0.002</span>
    <h3 class="timeline-header">Debrief Agent</h3>
    <div class="timeline-body">...</div>
  </div>
</div>
```

## Anti-Patterns

- Hardcoded URLs — always use `{% url %}` template tag
- Raw unescaped output — always rely on Django's auto-escaping or explicit `|escape`
- Forms without `{% csrf_token %}` — always include
- Rendering confidence/recommendation as plain text — always use colored badges
- Passing raw human feedback directly to an agent prompt visible in the UI — show the *translated* directives
- Arbitrary spacing — use Bootstrap 4 spacing utilities (`mt-3`, `px-4`, etc.)
- Inline styles — all custom styles in `static/css/`
- Heavy JS frameworks — vanilla ES6+ only; AdminLTE3's jQuery dependency is acceptable

## Template Directory Convention

```
templates/
├── adminlte/
│   └── base.html          # Project base extending AdminLTE3
├── pipeline/
│   ├── run_form.html       # Start a pipeline run
│   ├── run_detail.html     # Active run + human gate
│   └── matrix_partial.html # Reusable 4×4 matrix component
├── runs/
│   ├── run_list.html       # All historical runs
│   └── run_history.html    # Full iteration history for one run
└── evals/
    └── eval_results.html   # Eval dashboard
```
