import asyncio
import io
import logging
import os
import shutil
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.export.docx_exporter import export_schedule_to_docx
from app.models.schema import (
    GenerateScheduleResponse,
    ScheduleSlot,
    Teacher,
    ValidationIssue,
)
from app.parsers.curriculum_parser import (
    extract_grade11_class_track_mapping,
    parse_curriculum_docx,
)
from app.parsers.workload_parser import parse_workload_xlsx
from app.solver.scheduler import SolverStatus, generate_schedule

logger = logging.getLogger(__name__)

app = FastAPI(
    title="School Scheduler API",
    description="Backend API for parsing curriculum (.docx) and teacher workloads (.xlsx) and generating optimal school timetables with OR-Tools.",
    version="0.1.0",
)

# Enable CORS for frontend origin(s).
# ALLOWED_ORIGINS: comma-separated list of allowed origins (e.g. the deployed
# frontend URL). Falls back to local dev origins when unset.
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _allowed_origins_env:
    allowed_origins = [origin.strip() for origin in _allowed_origins_env.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SOLVER_TIME_LIMIT_SECONDS: default solver timeout when the client doesn't
# override it. Defaults to 30s for local/multi-core dev; set higher (e.g.
# 180-240) on a constrained single-core host, where the real dataset needs
# much more wall-clock time than a local dev machine's estimate suggests.
DEFAULT_TIME_LIMIT_SECONDS = int(os.getenv("SOLVER_TIME_LIMIT_SECONDS", "30"))


@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "service": "School Scheduler API",
        "status": "online",
        "version": "0.1.0",
    }


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/info")
def get_info() -> Dict[str, Any]:
    return {
        "app_name": "School Scheduler",
        "description": "Automated schedule generator for Russian educational standards (SanPiN compliant)",
        "features": [
            "DOCX Federal Curriculum Parser",
            "XLSX Teacher Workload Parser",
            "CP-SAT Constraint Programming Solver",
            "Interactive Timetable Grid",
        ],
    }


# -----------------------------------------------------------------------------
# Background job infrastructure.
#
# Schedule generation is CPU-bound (docx/xlsx parsing + a CP-SAT solve that can
# run for minutes). Running it inline inside an `async def` request handler
# blocks the single asyncio event loop for the whole duration - and while the
# loop is blocked, it can't accept or dispatch ANY other request, including
# Render's own health check. Render then concludes the instance is dead and
# restarts it mid-request, which is what caused "Failed to fetch" on the
# frontend.
#
# The fix: run the pipeline on a separate OS thread via a ThreadPoolExecutor,
# submitted through `loop.run_in_executor`, so the event loop thread is never
# occupied by it and stays free to answer other requests. This helps even on
# a single-core host because OR-Tools' CP-SAT solve is a native C++ call that
# releases the GIL while it runs, letting the event loop's thread still get
# scheduled in between; we've also set num_search_workers=1 via SOLVER_WORKERS
# for CP-SAT itself, so this isn't about parallelizing the solve, only about
# not starving the request-handling thread while it runs.
#
# Job results are kept in a plain in-memory dict. This is intentionally simple:
# it does NOT survive a process restart, and is NOT shared across multiple
# instances/workers - both fine for our single free-tier instance, but would
# need a real backing store (Redis, a DB table, etc.) to run with more than
# one worker or instance. Jobs are also never pruned from memory; acceptable
# at this app's demo scale, but worth knowing if it ever runs long-lived with
# heavy traffic.
# -----------------------------------------------------------------------------

_job_executor = ThreadPoolExecutor(max_workers=2)
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class JobCreatedResponse(BaseModel):
    """Returned immediately from POST /api/generate-schedule."""

    job_id: str = Field(..., description="Opaque identifier to poll for this job's status/result")
    status: Literal["pending"] = "pending"


class JobStatusResponse(BaseModel):
    """Returned from GET /api/jobs/{job_id}."""

    job_id: str
    status: Literal["pending", "done", "error"]
    result: Optional[GenerateScheduleResponse] = Field(
        default=None, description="Populated once status is 'done'"
    )
    error: Optional[str] = Field(default=None, description="Populated once status is 'error'")


def _run_schedule_pipeline_sync(
    file_paths: Dict[str, str],
    time_limit_seconds: int,
) -> Tuple[List[ScheduleSlot], SolverStatus, List[Teacher], List[ValidationIssue]]:
    """Synchronous parse -> validate -> solve pipeline over already-saved files.

    Contains no `await` and no FastAPI/Starlette request objects, so it's safe
    to run on a worker thread via ThreadPoolExecutor.
    """
    curriculum_requirements: List[Any] = []
    for file_key in ["up_noo", "up_ooo", "up_soo"]:
        try:
            curriculum_requirements.extend(parse_curriculum_docx(file_paths[file_key]))
        except Exception as e:
            raise RuntimeError(f"Failed to parse curriculum file '{file_key}': {e}") from e

    try:
        soo_class_track_map = extract_grade11_class_track_mapping(file_paths["up_soo"])
    except Exception as e:
        raise RuntimeError(f"Failed to extract Grade 11 track mapping from 'up_soo': {e}") from e

    try:
        teachers, assignments, warnings = parse_workload_xlsx(
            file_path=file_paths["workload"],
            curriculum=curriculum_requirements,
            soo_class_track_map=soo_class_track_map,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to parse workload file 'workload': {e}") from e

    try:
        schedule, solver_status = generate_schedule(
            assignments=assignments,
            time_limit_seconds=time_limit_seconds,
        )
    except Exception as e:
        raise RuntimeError(f"Solver execution failed: {e}") from e

    return schedule, solver_status, teachers, warnings


def _execute_job(job_id: str, temp_dir: str, file_paths: Dict[str, str], time_limit_seconds: int) -> None:
    """Runs the pipeline and stores its outcome in the job store.

    Executed on a worker thread (via ThreadPoolExecutor) - must not touch
    request/response objects, only plain data.
    """
    try:
        schedule, solver_status, teachers, warnings = _run_schedule_pipeline_sync(
            file_paths, time_limit_seconds
        )
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "done",
                "schedule": schedule,
                "solver_status": solver_status,
                "warnings": warnings,
                "teachers": teachers,
                "error": None,
            }
    except Exception as e:
        logger.error("Job %s failed: %s", job_id, e)
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "schedule": None,
                "solver_status": None,
                "warnings": None,
                "teachers": None,
                "error": str(e),
            }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _save_uploaded_files(
    up_noo: UploadFile,
    up_ooo: UploadFile,
    up_soo: UploadFile,
    workload: UploadFile,
) -> Tuple[str, Dict[str, str]]:
    """Saves the 4 uploads to a fresh temp dir.

    This is fast I/O (small files), done synchronously in the request handler
    before the CPU-heavy parse/solve work is handed off to a worker thread.
    """
    temp_dir = tempfile.mkdtemp(prefix="school_scheduler_")
    file_map = {
        "up_noo": (up_noo, os.path.join(temp_dir, "up_noo.docx")),
        "up_ooo": (up_ooo, os.path.join(temp_dir, "up_ooo.docx")),
        "up_soo": (up_soo, os.path.join(temp_dir, "up_soo.docx")),
        "workload": (workload, os.path.join(temp_dir, "workload.xlsx")),
    }

    file_paths: Dict[str, str] = {}
    for file_key, (upload_obj, dest_path) in file_map.items():
        try:
            contents = await upload_obj.read()
            with open(dest_path, "wb") as f:
                f.write(contents)
            file_paths[file_key] = dest_path
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.error("Failed to read/write uploaded file '%s': %s", file_key, e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to read uploaded file '{file_key}': {str(e)}",
            )

    return temp_dir, file_paths


def _get_job_or_404(job_id: str) -> Dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")
    return job


@app.post(
    "/api/generate-schedule",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start schedule generation as a background job; returns a job_id to poll",
)
async def generate_schedule_endpoint(
    up_noo: UploadFile = File(..., description="Curriculum file for grades 1-4 (.docx)"),
    up_ooo: UploadFile = File(..., description="Curriculum file for grades 5-9 (.docx)"),
    up_soo: UploadFile = File(..., description="Curriculum file for grades 10-11 (.docx)"),
    workload: UploadFile = File(..., description="Teacher workload matrix (.xlsx)"),
    time_limit_seconds: int = Query(
        default=DEFAULT_TIME_LIMIT_SECONDS, ge=1, le=300, description="Solver timeout in seconds"
    ),
) -> JobCreatedResponse:
    """Saves the uploads, starts the parse->validate->solve pipeline in the
    background, and returns immediately with a job_id to poll for the result.
    """
    temp_dir, file_paths = await _save_uploaded_files(up_noo, up_ooo, up_soo, workload)

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "pending",
            "schedule": None,
            "solver_status": None,
            "warnings": None,
            "teachers": None,
            "error": None,
        }

    loop = asyncio.get_running_loop()
    loop.run_in_executor(_job_executor, _execute_job, job_id, temp_dir, file_paths, time_limit_seconds)

    return JobCreatedResponse(job_id=job_id, status="pending")


@app.get(
    "/api/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll the status/result of a schedule generation job",
)
def get_job_status(job_id: str) -> JobStatusResponse:
    job = _get_job_or_404(job_id)

    result = None
    if job["status"] == "done":
        result = GenerateScheduleResponse(
            schedule=job["schedule"],
            solver_status=job["solver_status"].value,
            warnings=job["warnings"],
        )

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=result,
        error=job["error"],
    )


@app.get(
    "/api/jobs/{job_id}/export",
    summary="Download a finished job's schedule as a formatted DOCX document",
    response_description="Formatted Word document (.docx)",
)
def export_job_result(job_id: str) -> StreamingResponse:
    """Reuses the already-computed schedule/teachers from a finished job -
    does not re-run parsing or solving."""
    job = _get_job_or_404(job_id)

    if job["status"] == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job is still running; try again once its status is 'done'.",
        )
    if job["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Job failed and has no result to export: {job['error']}",
        )

    temp_docx = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    temp_docx_path = temp_docx.name
    temp_docx.close()

    try:
        export_schedule_to_docx(
            schedule=job["schedule"],
            teachers=job["teachers"],
            output_path=temp_docx_path,
        )
        with open(temp_docx_path, "rb") as f:
            docx_bytes = f.read()
    finally:
        try:
            os.remove(temp_docx_path)
        except Exception:
            pass

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="schedule.docx"'},
    )
