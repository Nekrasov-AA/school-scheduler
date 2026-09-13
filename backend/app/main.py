from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Any, Dict

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
