"""End-to-end pipeline test using the mock providers."""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_bugcopilot.db")
os.environ.setdefault("ISSUE_PROVIDER", "mock")
os.environ.setdefault("DOCS_PROVIDER", "mock")
os.environ.setdefault("CODE_PROVIDER", "mock")

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.models import Investigation  # noqa: E402
from backend.orchestrator.orchestrator import run_investigation  # noqa: E402
from backend.providers.factory import build_providers  # noqa: E402


@pytest.mark.asyncio
async def test_demo_investigation_completes():
    await init_db()
    async with SessionLocal() as s:
        inv = Investigation(issue_key="DEMO-1", triggered_by="test")
        s.add(inv)
        await s.commit()
        await s.refresh(inv)
        inv_id = inv.id

    issue_p, docs_p, code_p = build_providers()
    await run_investigation(
        investigation_id=inv_id,
        issue_key="DEMO-1",
        repos=["acme/web-app", "acme/permissions-service"],
        issue_provider=issue_p,
        docs_provider=docs_p,
        code_provider=code_p,
    )

    async with SessionLocal() as s:
        inv = await s.get(Investigation, inv_id)
        assert inv.status == "COMPLETED", inv.error


if __name__ == "__main__":
    asyncio.run(test_demo_investigation_completes())
    print("OK")
