# School Scheduler

A school scheduling tool that parses curriculum documents (`.docx`) and teacher workload spreadsheets (`.xlsx`), then uses a constraint solver (Google OR-Tools) to generate an optimal class timetable.

## Quick Start

1. Start both backend and frontend services:

```bash
docker-compose up
```

2. Open [http://localhost:5173](http://localhost:5173) in your browser.

- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

