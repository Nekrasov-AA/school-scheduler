import os
import time
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_happy_path_generate_schedule():
    """Happy path: Upload all 4 real fixture files, verify optimal schedule generation."""
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

        response = client.post(
            "/api/generate-schedule",
            files=files,
            params={"time_limit_seconds": 30},
        )

    elapsed = time.time() - start_time

    print("\n==================== HAPPY PATH API RUN ====================")
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Total End-to-End Elapsed Time: {elapsed:.2f} seconds")

    assert response.status_code == 200, f"Expected 200, got: {response.status_code} - {response.text}"
    data = response.json()

    print(f"Solver Status in Response: {data.get('solver_status')}")
    print(f"Scheduled Slots Count: {len(data.get('schedule', []))}")
    print(f"Warnings Count: {len(data.get('warnings', []))}")

    assert data["solver_status"] == "optimal"
    assert len(data["schedule"]) == 2242, f"Expected 2242 scheduled slots, got: {len(data['schedule'])}"
    assert isinstance(data["warnings"], list)


def test_failure_invalid_file_format():
    """Failure case: Upload workload.xlsx in up_noo slot (wrong format), confirm 422 with clear message."""
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

        response = client.post(
            "/api/generate-schedule",
            files=files,
            params={"time_limit_seconds": 10},
        )

    print("\n==================== FAILURE CASE (WRONG FILE FORMAT) ====================")
    print(f"HTTP Status Code: {response.status_code}")
    print(f"Response Detail: {response.json()}")

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "up_noo" in data["detail"].lower()


def test_missing_required_file():
    """Missing file case: Omit one required field ('workload'), confirm 422 validation error."""
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
