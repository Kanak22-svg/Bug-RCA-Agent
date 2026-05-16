# Bug Investigation Copilot

A read-only orchestration service that ingests a Jira bug, gathers context from
**Confluence** (via the Atlassian Rovo MCP server) and **GitHub** (via the
GitHub MCP server), then produces an evidence-backed report:

- likely code locations
- likely **intentional** vs **regression** classification
- suspicious commits / PRs
- recommended next action
- supporting Confluence pages + related Jira tickets

Triggered manually from the UI ("Analyze Bug"). It **never writes** to Jira,
Confluence, or GitHub — every MCP tool call is checked against a read-only
allow-list ([readonly_guard.py](backend/security/readonly_guard.py)).

## Architecture

```
                ┌──────────────────┐
   Browser  ──► │  FastAPI (api)   │  POST /api/investigations
                └─────────┬────────┘
                          │ background task
                          ▼
                ┌──────────────────┐
                │   Orchestrator   │  state machine
                └─────────┬────────┘
                          │
       ┌──────────────────┼──────────────────────────────┐
       ▼                  ▼                              ▼
 IssueProvider      DocsProvider                  CodeProvider
 (Jira via MCP)     (Confluence via MCP)          (GitHub via MCP)
       │                  │                              │
       ▼                  ▼                              ▼
        ─────────► Investigation Engine ◄──────────────
        intake → context → localize → intent → regression → report
                          │
                          ▼
                   SQLite (state, artifacts, candidates, report)
                          │
                          ▼
                       Frontend (read-only)
```

Pipeline states: `CREATED → FETCHING_CONTEXT → PARSING_REPRO → LOCALIZING_CODE
→ ANALYZING_INTENT → FINDING_REGRESSION → GENERATING_REPORT → COMPLETED`.

## Layout

| Path | Purpose |
| --- | --- |
| [backend/main.py](backend/main.py) | FastAPI entrypoint + static frontend |
| [backend/api/investigations.py](backend/api/investigations.py) | REST routes |
| [backend/orchestrator/orchestrator.py](backend/orchestrator/orchestrator.py) | State machine |
| [backend/engine/](backend/engine) | Intake, localization, intent, regression, report |
| [backend/providers/base.py](backend/providers/base.py) | `IssueProvider` / `DocsProvider` / `CodeProvider` interfaces |
| [backend/providers/atlassian_mcp.py](backend/providers/atlassian_mcp.py) | Atlassian Rovo MCP adapter |
| [backend/providers/github_mcp.py](backend/providers/github_mcp.py) | GitHub MCP adapter |
| [backend/providers/mock_provider.py](backend/providers/mock_provider.py) | Offline mock for `DEMO-1` |
| [backend/security/readonly_guard.py](backend/security/readonly_guard.py) | MCP read-only allow-list |
| [frontend/](frontend) | Minimal single-page UI |

## Run locally (mock providers, no credentials)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.main
```

Open <http://localhost:8000>, leave `DEMO-1` as the issue key, and click
**Analyze Bug**. The full pipeline runs against the in-memory mock and the
generated report renders in the page.

## Switch to real MCP servers

Edit `.env`:

```
ISSUE_PROVIDER=mcp
DOCS_PROVIDER=mcp
CODE_PROVIDER=mcp

ATLASSIAN_MCP_URL=https://mcp.atlassian.com/v1/sse
ATLASSIAN_MCP_TOKEN=<your atlassian oauth token>

GITHUB_MCP_URL=https://api.githubcopilot.com/mcp
GITHUB_MCP_TOKEN=<your GitHub token>
```

Local stdio GitHub MCP server is also supported — set `GITHUB_MCP_STDIO=1`
and `GITHUB_MCP_COMMAND=...`.

If a deployment renames a tool, update both the adapter and the allow-list in
[readonly_guard.py](backend/security/readonly_guard.py). Any tool call not on
the allow-list is refused before it leaves the process.

## Optional LLM

If `OPENAI_API_KEY` is set, the intent analyzer asks an OpenAI-compatible model
to weigh the evidence. Otherwise it falls back to the deterministic heuristic
in [intent_analyzer.py](backend/engine/intent_analyzer.py) — the system works
end-to-end without any LLM.

## Test

```bash
pip install pytest pytest-asyncio
pytest -q
```

[tests/test_pipeline.py](tests/test_pipeline.py) runs the full pipeline against
the mock providers and asserts the investigation reaches `COMPLETED`.

## Roadmap (per spec)

- **MVP (this repo):** intake → context → localize → intent → regression → report → UI
- **Phase 2:** confidence scoring refinements, owner inference, release correlation, Slack notifications
- **Phase 3:** optional repo-local scripts, deeper diff reasoning, selective automated replay
