# Proposal Pipeline AI — Claude Project Context

## Project Overview
**Proposal Pipeline AI** is a multi-agent consulting tool that turns raw client intake materials and discovery transcripts into polished, structured proposals with a human-in-the-loop refinement loop.

- **Framework**: Django 6.0.4 — Python 3.x
- **Language**: Python 3.x with type annotations throughout
- **Database**: SQLite3 (`db.sqlite3`) via Django ORM
- **AI Layer**: OpenRouter via OpenAI-compatible SDK (`openai`) — free-tier models, base URL set to `https://openrouter.ai/api/v1`
- **Schema Validation**: Pydantic v2 (`pydantic==2.11.7`) at every agent boundary
- **Frontend**: Django templates + Bootstrap 4 (via `django-bootstrap4`) + AdminLTE3 (via `django-adminlte3`)
- **Task Queue / Retry**: `tenacity` and `backoff` for API retry logic
- **Testing**: `pytest` + `pytest-flask`

---

## Pipeline Architecture

```
[Intake docs + transcripts]
        │
        ▼
┌─────────────────┐
│  Debrief Agent  │  → ClientMatrix (Pydantic model) — 4×4 structured grid
└─────────────────┘
        │
        ▼
┌─────────────────┐
│ Proposal Agent  │  → ProposalDocument (Pydantic model) — markdown proposal
└─────────────────┘
        │
        ▼
┌─────────────────┐
│  Review Agent   │  → ReviewResult (Pydantic model) — critique + translated feedback
└─────────────────┘
        │
        ▼
  [Human Gate]  ──── if rejected, loops back to Proposal Agent
        │              with structured FeedbackHistory
        ▼
  [Approved Proposal]
```

**Key invariant:** Items with `contradicted` or `low` confidence in the matrix must appear in the proposal's Open Questions section — never as confident statements.

---

## Project Structure

```
proposal-pipeline-AI/
├── proposal_pipeline/        # Django project config (settings, urls, wsgi, asgi)
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── <app>/                    # Django apps live here (e.g. pipeline/, runs/, evals/)
│   ├── agents/               # Agent implementations (debrief.py, proposal.py, review.py)
│   ├── schemas/              # Pydantic models for inter-agent contracts
│   ├── tools/                # Claude tool definitions (CRM lookup, pricing lookup, etc.)
│   ├── models.py             # Django ORM models for persistence
│   ├── views.py              # Django views (human-in-the-loop UI)
│   └── urls.py
├── templates/                # Django HTML templates (AdminLTE3 layout)
├── static/                   # CSS, JS, images
│   ├── css/
│   ├── js/
│   └── images/
├── runs/                     # Committed run outputs (per transcript, per iteration)
├── assignment/               # Original brief and intake data (read-only reference)
│   └── data/
│       ├── intake.md
│       ├── transcript_a.md
│       └── transcript_b.md
├── manage.py
├── requirements.txt
├── db.sqlite3
└── .env                      # API keys and local overrides (never commit)
```

---

## Agent Contracts (Pydantic Schemas)

All inter-agent data must be validated Pydantic models. JSON-in-prompt with regex extraction is forbidden.

### ClientMatrix
- 4 rows: `business`, `technical`, `operational`, `strategic`
- 4 columns: `pain_points`, `desired_state`, `success_criteria`, `risks_unknowns`
- Each cell: list of `MatrixItem(statement, confidence, source_excerpt, contradiction_note?)`
- `confidence`: `"high" | "medium" | "low" | "contradicted"`
- **Contradictions must be preserved as `contradicted` items, never flattened.**

### ProposalDocument
- Sections in order: Executive Summary, Understanding, Approach, Phases & Timeline, Pricing Approach, Open Questions
- `contradicted` and `low` confidence matrix items → Open Questions only

### ReviewResult
- `issues`: list of `ReviewIssue(severity, location, description, suggested_fix)`
- `recommendation`: `"approve" | "revise" | "escalate_to_human"`
- `translated_feedback`: structured directives for the Proposal Agent (not raw human text)

### FeedbackHistory
- Full history is preserved across iterations (deliberate choice — allows divergence detection)
- Each entry: `iteration`, `human_raw`, `translated_directives`, `proposal_snapshot_path`

---

## AI / OpenRouter Integration

- Use `openai` SDK with `base_url="https://openrouter.ai/api/v1"` and `api_key=OPENROUTER_API_KEY`
- No LangChain or LangGraph wrapper — raw SDK calls only
- Model: `openrouter/free` (OpenRouter auto-routes to best available free model)
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Structured output via `response_format={"type": "json_object"}` — required for all agent calls that return Pydantic models
- Tool calls wired via OpenRouter's tool-use support (OpenAI-compatible `tools` parameter) — not bolted-on string parsing
- Observability: every call logs `agent_name`, `model`, `prompt_tokens`, `completion_tokens`, `latency_ms` (cost tracked as $0 for free tier but structure preserved for paid-tier compatibility)
- Retry on rate limits and transient errors using `tenacity` with exponential backoff
- Schema validation failures trigger a re-prompt with the validation error in context (one retry max)
- `OPENROUTER_API_KEY` loaded from `.env` via `python-decouple`

---

## Django Conventions

- Apps registered in `INSTALLED_APPS` — one app per domain (`pipeline`, `runs`, `evals`)
- ORM models in `models.py` per app; migrations via `python manage.py makemigrations && migrate`
- Views are thin — business logic lives in `agents/` and `schemas/`, not in views
- URL namespacing: `app_name` in each app's `urls.py`, included in root `proposal_pipeline/urls.py`
- Settings loaded from `.env` via `python-decouple` — never hardcode secrets
- `TEMPLATES['DIRS']` should include the top-level `templates/` directory

---

## Running the Project

```bash
# Activate venv
venv\Scripts\Activate.ps1   # Windows PowerShell

# Run dev server
python manage.py runserver

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Run evals
python manage.py eval              # or: pytest evals/
# or via Makefile:
make eval
```

---

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Django apps | lowercase, short | `pipeline`, `runs`, `evals` |
| Agent modules | `snake_case` noun | `debrief_agent.py`, `proposal_agent.py` |
| Pydantic models | `PascalCase` | `ClientMatrix`, `ProposalDocument`, `ReviewResult` |
| Django models | `PascalCase` | `RunRecord`, `IterationLog` |
| Views | `snake_case` functions or `PascalCase` CBVs | `run_pipeline`, `HumanGateView` |
| URL names | `snake_case` with namespace | `pipeline:run`, `runs:detail` |
| Templates | `snake_case`, folder-namespaced | `pipeline/run_form.html` |
| Pydantic fields | `snake_case` | `source_excerpt`, `contradiction_note` |
| DB columns | `snake_case` | `iteration_number`, `cost_usd` |

---

## Code Style

- Type-annotate all function signatures — `def run_debrief(transcript: str, intake: str) -> ClientMatrix:`
- No raw `json.loads()` on agent output — always deserialize via Pydantic `.model_validate()`
- Keep views thin: no Claude calls in views, no ORM queries in agent code
- Use `python-decouple` `config()` for all env var access
- One tool definition file per tool; register all tools in a central `tools/__init__.py`
- Structured logs as JSON to a file per run (`runs/<run_id>/log.jsonl`)

---

## What to Avoid

- Do not parse agent output with regex or string manipulation — use Pydantic
- Do not call Claude from Django views — queue it or call from a management command
- Do not commit `.env`, `db.sqlite3` contents, or `runs/` binary artifacts
- Do not add frontend frameworks (React, Vue) — Django templates + Bootstrap only
- Do not skip schema validation on agent boundaries, even for prototypes
- Do not pass raw human feedback verbatim to the Proposal Agent — always translate via Review Agent
- Do not create `.md` documentation files unless explicitly requested
