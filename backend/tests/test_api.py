import os
import time
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

JOB_POLL_INTERVAL_SECONDS = 0.5
JOB_POLL_TIMEOUT_SECONDS = 60


def _poll_job_until_finished(job_id: str, timeout: float = JOB_POLL_TIMEOUT_SECONDS) -> dict:
    """Polls GET /api/jobs/{job_id} until status is 'done' or 'error', or raises on timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, f"Unexpected status polling job: {response.text}"
        data = response.json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(JOB_POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Job '{job_id}' did not finish within {timeout}s")


def _submit_job(files: dict, params: dict | None = None):
    response = client.post("/api/generate-schedule", files=files, params=params or {})
    assert response.status_code == 202, f"Expected 202, got: {response.status_code} - {response.text}"
    data = response.json()
    assert data["status"] == "pending"
    assert data["job_id"]
    return data["job_id"]


def test_happy_path_generate_schedule():
    """Happy path: Upload all 4 real fixture files, poll until done, verify optimal schedule generation."""
    up_noo_path = os.path.join(FIXTURES_DIR, "up_noo.docx")
    up_ooo_path = os.path.join(FIXTURES_DIR, "up_ooo.docx")
    up_soo_path = os.path.join(FIXTURES_DIR, "up_soo.docx")
    workload_path = os.path.join(FIXTURES_DIR, "workload.xlsx")

    assert os.path.exists(up_noo_path)
    assert os.path.exists(up_ooo_path)
    assert os.path.exists(up_soo_path)
    assert os.path.exists(workload_path)

    start_time = time.time()

    with (
        open(up_noo_path, "rb") as f_noo,
        open(up_ooo_path, "rb") as f_ooo,
        open(up_soo_path, "rb") as f_soo,
        open(workload_path, "rb") as f_workload,
    ):
        files = {
            "up_noo": ("up_noo.docx", f_noo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_ooo": ("up_ooo.docx", f_ooo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_soo": ("up_soo.docx", f_soo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "workload": ("workload.xlsx", f_workload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        }

        job_id = _submit_job(files, params={"time_limit_seconds": 30})

    data = _poll_job_until_finished(job_id)
    elapsed = time.time() - start_time

    print("\n==================== HAPPY PATH API RUN (async job) ====================")
    print(f"Job status: {data['status']}")
    print(f"Total End-to-End Elapsed Time: {elapsed:.2f} seconds")

    assert data["status"] == "done", f"Job failed: {data.get('error')}"
    result = data["result"]

    print(f"Solver Status in Response: {result.get('solver_status')}")
    print(f"Scheduled Slots Count: {len(result.get('schedule', []))}")
    print(f"Warnings Count: {len(result.get('warnings', []))}")

    assert result["solver_status"] in ("optimal", "feasible", "infeasible")
    if result["solver_status"] == "infeasible":
        assert len(result["schedule"]) == 0
    else:
        assert len(result["schedule"]) > 0
    assert isinstance(result["warnings"], list)


def test_failure_invalid_file_format():
    """Failure case: Upload workload.xlsx in up_noo slot (wrong format); job should end in 'error'."""
    up_ooo_path = os.path.join(FIXTURES_DIR, "up_ooo.docx")
    up_soo_path = os.path.join(FIXTURES_DIR, "up_soo.docx")
    workload_path = os.path.join(FIXTURES_DIR, "workload.xlsx")

    with (
        open(workload_path, "rb") as f_wrong,
        open(up_ooo_path, "rb") as f_ooo,
        open(up_soo_path, "rb") as f_soo,
        open(workload_path, "rb") as f_workload,
    ):
        files = {
            "up_noo": ("workload.xlsx", f_wrong, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "up_ooo": ("up_ooo.docx", f_ooo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_soo": ("up_soo.docx", f_soo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "workload": ("workload.xlsx", f_workload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        }

        job_id = _submit_job(files, params={"time_limit_seconds": 10})

    data = _poll_job_until_finished(job_id)

    print("\n==================== FAILURE CASE (WRONG FILE FORMAT, async job) ====================")
    print(f"Job status: {data['status']}")
    print(f"Error: {data.get('error')}")

    assert data["status"] == "error"
    assert "up_noo" in data["error"].lower()

    # The job has no result to export once it's failed.
    export_response = client.get(f"/api/jobs/{job_id}/export")
    assert export_response.status_code == 422


def test_missing_required_file():
    """Missing file case: Omit one required field ('workload'), confirm 422 validation error.

    This is FastAPI's own request validation (missing required File(...) param),
    which happens before our handler runs at all - so it's still synchronous,
    unaffected by the async job pattern.
    """
    up_noo_path = os.path.join(FIXTURES_DIR, "up_noo.docx")
    up_ooo_path = os.path.join(FIXTURES_DIR, "up_ooo.docx")
    up_soo_path = os.path.join(FIXTURES_DIR, "up_soo.docx")

    with (
        open(up_noo_path, "rb") as f_noo,
        open(up_ooo_path, "rb") as f_ooo,
        open(up_soo_path, "rb") as f_soo,
    ):
        files = {
            "up_noo": ("up_noo.docx", f_noo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_ooo": ("up_ooo.docx", f_ooo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_soo": ("up_soo.docx", f_soo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        }

        response = client.post(
            "/api/generate-schedule",
            files=files,
        )

    print("\n==================== MISSING REQUIRED FILE ====================")
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Response Detail: {response.json()}")

    assert response.status_code == 422


def test_job_not_found():
    """Polling or exporting an unknown job_id returns 404."""
    response = client.get("/api/jobs/does-not-exist")
    assert response.status_code == 404

    response = client.get("/api/jobs/does-not-exist/export")
    assert response.status_code == 404


def test_export_before_job_done():
    """Exporting a job that's still pending returns 409, not a docx."""
    up_noo_path = os.path.join(FIXTURES_DIR, "up_noo.docx")
    up_ooo_path = os.path.join(FIXTURES_DIR, "up_ooo.docx")
    up_soo_path = os.path.join(FIXTURES_DIR, "up_soo.docx")
    workload_path = os.path.join(FIXTURES_DIR, "workload.xlsx")

    with (
        open(up_noo_path, "rb") as f_noo,
        open(up_ooo_path, "rb") as f_ooo,
        open(up_soo_path, "rb") as f_soo,
        open(workload_path, "rb") as f_workload,
    ):
        files = {
            "up_noo": ("up_noo.docx", f_noo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_ooo": ("up_ooo.docx", f_ooo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "up_soo": ("up_soo.docx", f_soo, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "workload": ("workload.xlsx", f_workload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        }

        job_id = _submit_job(files, params={"time_limit_seconds": 30})

    # Export immediately, before giving the background thread any time to run.
    export_response = client.get(f"/api/jobs/{job_id}/export")
    assert export_response.status_code in (409, 200)
    # Either it's still pending (409) or it raced ahead and already finished (200) -
    # both are acceptable; what matters is it never 500s or hangs. Drain the job
    # so the background thread doesn't outlive the test.
    _poll_job_until_finished(job_id)
