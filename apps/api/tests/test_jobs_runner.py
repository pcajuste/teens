from __future__ import annotations


def test_noop_job_runs_with_valid_secret(client, settings):
    response  = client.post(
        "/internal/jobs/run/noop_heartbeat",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )
    assert response .status_code == 200
    assert response .json() == {"job": "noop_heartbeat", "status": "ok"}


def test_wrong_secret_returns_401(client):
    response  = client.post(
        "/internal/jobs/run/noop_heartbeat",
        headers={"X-Jobs-Runner-Secret": "wrong-secret"},
    )
    assert response .status_code == 401
    assert response .json()["error"]["code"] == "invalid_jobs_runner_secret"


def test_unknown_job_returns_404(client, settings):
    response  = client.post(
        "/internal/jobs/run/does_not_exist",
        headers={"X-Jobs-Runner-Secret": settings.jobs_runner_secret},
    )
    assert response .status_code == 404
    assert response .json()["error"]["code"] == "unknown_job"


def test_health_endpoint_still_works(client):
    response  = client.get("/health")
    assert response .status_code == 200
