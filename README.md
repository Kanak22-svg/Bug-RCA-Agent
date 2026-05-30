# Bug RCA (Root Cause Analysis) Agent

An AI-driven root cause analysis agent that analyzes logs, stack traces, bug reports, and code repositories to automatically identify root causes, classify issues, and recommend fixes.

## Stack

- **Python** — Core language
- **FastAPI** — Async REST API framework
- **Claude API (Anthropic)** — LLM-powered intelligent analysis
- **PostgreSQL** — Persistent storage for investigations and reports
- **Docker** — Containerized deployment with docker-compose
- **SQLAlchemy** — Async ORM with Alembic migrations
- **Redis** — Job queue for async investigation processing

## Features

### Core Investigation Pipeline
- **Bug Report Analysis** — Accepts Jira issue keys, fetches full context (issue, comments, linked tickets, team metadata)
- **Log & Stack Trace Analysis** — Parses raw logs, stack traces, and error messages from Python, Java, JavaScript, Go, and C#
- **Code Localization** — Maps bug symptoms to candidate files and functions using keyword matching, commit history, and component analysis
- **Intent Classification** — Determines if behavior is intentional (documented, tested) or a regression (undocumented, accidental side-effect)
- **Regression Detection** — Identifies suspicious commits and PRs by correlating file changes, commit timing, and PR descriptions
- **Fix Recommendation** — Suggests specific code changes, assigns to commit owners, and provides actionable next steps

### Integrations (via Provider Abstraction Layer)
- **Jira** — Read issue details, comments, linked tickets, team metadata
- **Confluence** — Search design docs, specs, release notes for behavior context
- **GitHub** — Browse code, commits, PRs, blame history for code analysis
- **Mock Provider** — Full demo mode with realistic hardcoded data for testing

### LLM-Enhanced Analysis
- Falls back gracefully to rule-based heuristics when API key is not configured
- Uses Claude API for:
  - Intelligent bug classification with evidence reasoning
  - Executive summary generation
  - Code fix suggestions
  - Log/stack trace root cause explanation

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FastAPI Backend                    │
├─────────────┬─────────────┬─────────────────────────┤
│  /api/      │  /api/      │  /api/                  │
│  health     │  investigations  │  analyze/logs       │
├─────────────┴─────────────┴─────────────────────────┤
│              Investigation Service                    │
├──────────────────────────────────────────────────────┤
│              Investigation Orchestrator               │
│  ┌────────┬───────────┬──────────┬────────────────┐ │
│  │ Intake │ Localizer │ Intent   │ Regression     │ │
│  │        │           │ Analyzer │ Finder         │ │
│  ├────────┴───────────┴──────────┴────────────────┤ │
│  │ LLM Analyzer (Claude API — optional)           │ │
│  ├────────────────────────────────────────────────┤ │
│  │ Log Analyzer (regex-based stack trace parser)  │ │
│  └────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────┤
│           Provider Abstraction Layer                  │
│  ┌──────────────┬───────────────┬────────────────┐  │
│  │ IssueProvider│ DocsProvider  │ CodeProvider   │  │
│  ├──────────────┼───────────────┼────────────────┤  │
│  │ Mock (demo)  │ Mock (demo)   │ Mock (demo)    │  │
│  │ Jira MCP     │ Confluence MCP│ GitHub MCP     │  │
│  └──────────────┴───────────────┴────────────────┘  │
├──────────────────────────────────────────────────────┤
│  PostgreSQL │ Redis │ SQLite (dev)                    │
└──────────────────────────────────────────────────────┘
```

## Quick Start

### Local Development (SQLite)

```bash
# Clone the repository
git clone https://github.com/Kanak22-svg/bug-rca-agent.git
cd bug-rca-agent/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY for LLM features (optional)

# Run the server
uvicorn app.main:app --reload --port 8000

# API docs available at http://localhost:8000/docs
```

### Docker (PostgreSQL + Redis)

```bash
# Clone and start all services
git clone https://github.com/Kanak22-svg/bug-rca-agent.git
cd bug-rca-agent

# Optional: set API key for LLM features
export ANTHROPIC_API_KEY=sk-ant-your-key

# Start services
docker-compose up --build

# API available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## API Endpoints

### Investigations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/investigations` | Create and run a new investigation |
| `GET` | `/api/investigations` | List all investigations (paginated) |
| `GET` | `/api/investigations/{id}` | Get full investigation with report |
| `GET` | `/api/investigations/{id}/status` | Poll investigation progress |
| `POST` | `/api/investigations/{id}/rerun` | Re-run an investigation |
| `PATCH` | `/api/investigations/{id}/pin` | Toggle pin/favorite |
| `DELETE` | `/api/investigations/{id}` | Delete investigation |
| `GET` | `/api/investigations/stats` | Dashboard statistics |

### Log Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze/logs` | Analyze raw logs/stack traces |
| `POST` | `/api/analyze/stacktrace` | Analyze stack traces (alias) |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health check |

## Example: Create Investigation

```bash
curl -X POST http://localhost:8000/api/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "issue_key": "PROJ-1234",
    "repo_override": "web-app",
    "scope": {
      "search_jira": true,
      "search_confluence": true,
      "search_github": true,
      "deep_history": false
    }
  }'
```

Response includes:
- Bug snapshot with full Jira details
- Code candidates ranked by confidence
- Suspicious commits with suspicion levels
- Classification (LIKELY_REGRESSION / LIKELY_INTENTIONAL / UNCLEAR)
- Executive summary and evidence timeline
- Recommended next action with suggested code fix

## Example: Analyze Stack Trace

```bash
curl -X POST http://localhost:8000/api/analyze/logs \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "Traceback (most recent call last):\n  File \"app/views.py\", line 42, in export_report\n    data = get_report_data(report_id)\n  File \"app/services.py\", line 88, in get_report_data\n    raise PermissionError(\"User does not have export access\")\nPermissionError: User does not have export access",
    "title": "Export failing for admin users"
  }'
```

## Database Schema

Core tables:
- `investigations` — Investigation jobs with status tracking
- `bug_snapshots` — Normalized bug data from Jira
- `context_artifacts` — Jira tickets, Confluence docs, GitHub data
- `code_candidates` — Ranked suspect code locations
- `commit_candidates` — Suspicious commits and PRs
- `investigation_reports` — Final analysis reports
- `progress_steps` — Pipeline step tracking
- `audit_logs` — Action audit trail

## Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Environment configuration
│   ├── database.py             # Async SQLAlchemy setup
│   ├── api/
│   │   ├── router.py           # API router aggregation
│   │   ├── health.py           # Health check endpoint
│   │   ├── investigations.py   # Investigation CRUD endpoints
│   │   └── analyze.py          # Log analysis endpoints
│   ├── models/
│   │   ├── investigation.py    # SQLAlchemy ORM models
│   │   └── schemas.py          # Pydantic request/response schemas
│   ├── providers/
│   │   ├── base.py             # Abstract provider interfaces
│   │   ├── mock_provider.py    # Mock data for demo/testing
│   │   ├── jira_provider.py    # Jira MCP adapter (Phase 2)
│   │   ├── confluence_provider.py  # Confluence MCP adapter (Phase 2)
│   │   └── github_provider.py  # GitHub MCP adapter (Phase 2)
│   ├── engine/
│   │   ├── orchestrator.py     # Investigation pipeline coordinator
│   │   ├── intake.py           # Bug data normalization
│   │   ├── localization.py     # Code location finder
│   │   ├── intent_analyzer.py  # Intentional vs regression classifier
│   │   ├── regression_finder.py # Suspicious commit identifier
│   │   ├── recommendation.py   # Next action recommender
│   │   ├── report_generator.py # Report assembler
│   │   ├── log_analyzer.py     # Log/stack trace parser
│   │   └── llm_analyzer.py     # Claude API integration
│   └── services/
│       └── investigation_service.py  # Business logic layer
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Roadmap

- [x] Core investigation pipeline
- [x] Mock provider with realistic demo data
- [x] Log and stack trace analysis
- [x] LLM-powered analysis (Claude API)
- [x] Docker + PostgreSQL deployment
- [ ] React frontend with investigation dashboard
- [ ] Real Jira/Confluence MCP integration
- [ ] Real GitHub MCP integration
- [ ] WebSocket for real-time progress updates
- [ ] Elasticsearch for log indexing and search
- [ ] Slack notification integration
