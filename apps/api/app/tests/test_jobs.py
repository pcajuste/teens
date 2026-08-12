from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.jobs.runner import run_job


def test_noop_job_runs_directly() -> None:
    assert run_job("noop") == {"ran": "noop", "result": "ok"}


def test_unknown_job_raises_keyerror() -> None:
    import pytest

    with pytest.raises(KeyError):
        run_job("does-not-exist")


def test_internal_jobs_endpoint_requires_secret(client: TestClient) -> None:
    resp = client.post("/internal/jobs/run/noop")
    assert resp.status_code == 401


def test_internal_jobs_endpoint_runs_with_correct_secret(
    client: TestClient, settings: Settings
) -> None:
    resp = client.post(
        "/internal/jobs/run/noop",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ran": "noop", "result": "ok"}
