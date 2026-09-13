import logging
import os
import shutil
import tempfile
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.models.schema import GenerateScheduleResponse
from app.parsers.curriculum_parser import (
    extract_grade11_class_track_mapping,
    parse_curriculum_docx,
)
from app.parsers.workload_parser import parse_workload_xlsx
from app.solver.scheduler import generate_schedule

logger = logging.getLogger(__name__)

app = FastAPI(
    title="School Scheduler API",
    description="Backend API for parsing curriculum (.docx) and teacher workloads (.xlsx) and generating optimal school timetables with OR-Tools.",
    version="0.1.0",
)

# Enable CORS for frontend origin(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post(
    "/api/generate-schedule",
    response_model=GenerateScheduleResponse,
    summary="Generate a school schedule from uploaded curriculum and workload files",
)
async def generate_schedule_endpoint(
    up_noo: UploadFile = File(..., description="Curriculum file for grades 1-4 (.docx)"),
    up_ooo: UploadFile = File(..., description="Curriculum file for grades 5-9 (.docx)"),
    up_soo: UploadFile = File(..., description="Curriculum file for grades 10-11 (.docx)"),
    workload: UploadFile = File(..., description="Teacher workload matrix (.xlsx)"),
    time_limit_seconds: int = Query(default=30, ge=1, le=300, description="Solver timeout in seconds"),
) -> GenerateScheduleResponse:
    """Full schedule generation pipeline:
    1. Parse three curriculum documents (.docx) -> list[CurriculumRequirement].
    2. Extract Grade 11 class-to-track mapping from up_soo.docx.
    3. Parse teacher workload spreadsheet (.xlsx) with curriculum cross-referencing -> list[Assignment].
    4. Solve Constraint Satisfaction Problem with Google OR-Tools CP-SAT -> list[ScheduleSlot].
    """
    temp_dir = tempfile.mkdtemp(prefix="school_scheduler_")

    try:
        # Save uploaded files to disk for path-based parsers
        file_map = {
            "up_noo": (up_noo, os.path.join(temp_dir, "up_noo.docx")),
            "up_ooo": (up_ooo, os.path.join(temp_dir, "up_ooo.docx")),
            "up_soo": (up_soo, os.path.join(temp_dir, "up_soo.docx")),
            "workload": (workload, os.path.join(temp_dir, "workload.xlsx")),
        }

        for file_key, (upload_obj, dest_path) in file_map.items():
            try:
                contents = await upload_obj.read()
                with open(dest_path, "wb") as f:
                    f.write(contents)
            except Exception as e:
                logger.error("Failed to read/write uploaded file '%s': %s", file_key, e)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Failed to read uploaded file '{file_key}': {str(e)}",
                )

        # 1. Parse curriculum files
        curriculum_requirements = []
        for file_key in ["up_noo", "up_ooo", "up_soo"]:
            path = file_map[file_key][1]
            try:
                reqs = parse_curriculum_docx(path)
                curriculum_requirements.extend(reqs)
            except Exception as e:
                logger.error("Error parsing curriculum file '%s': %s", file_key, e)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Failed to parse curriculum file '{file_key}': {str(e)}",
                )

        # 2. Extract Grade 11 class-to-track mapping from up_soo
        try:
            soo_class_track_map = extract_grade11_class_track_mapping(file_map["up_soo"][1])
        except Exception as e:
            logger.error("Error extracting Grade 11 track mapping from 'up_soo': %s", e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to extract Grade 11 track mapping from 'up_soo': {str(e)}",
            )

        # 3. Parse teacher workload spreadsheet
        try:
            teachers, assignments, warnings = parse_workload_xlsx(
                file_path=file_map["workload"][1],
                curriculum=curriculum_requirements,
                soo_class_track_map=soo_class_track_map,
            )
        except Exception as e:
            logger.error("Error parsing workload file 'workload': %s", e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to parse workload file 'workload': {str(e)}",
            )

        # 4. Generate schedule via CP-SAT solver
        try:
            schedule, solver_status = generate_schedule(
                assignments=assignments,
                time_limit_seconds=time_limit_seconds,
            )
        except Exception as e:
            logger.error("Error running scheduler solver: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Solver execution failed: {str(e)}",
            )

        return GenerateScheduleResponse(
            schedule=schedule,
            solver_status=solver_status.value,
            warnings=warnings,
        )

    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning("Failed to clean up temp dir %s: %s", temp_dir, e)

