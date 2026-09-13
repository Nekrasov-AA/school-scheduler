# Deploying to Render

This project deploys as two separate Render services, defined together in
[`render.yaml`](../render.yaml) at the repo root:

- **school-scheduler-backend** — Docker web service (FastAPI + OR-Tools),
  built from `backend/Dockerfile`.
- **school-scheduler-frontend** — Static site (Vite build output), built
  from the `frontend/` directory.

## Deploying via Blueprint

1. Push `render.yaml` to the branch you want deployed (e.g. `main`) on GitHub.
2. In the Render dashboard, choose **New > Blueprint**.
3. Connect the repository. Render will detect `render.yaml` and show both
   services for review.
4. Click **Apply** / **New Blueprint Instance**. Render creates both services
   and kicks off their first builds.

## Manual steps after the first deploy

The two services need each other's URL, but neither URL exists until the
service is first created — so this can't be wired up automatically in
`render.yaml`. Render's Blueprint `fromService` field can only inject a bare
hostname or `host:port` into an env var, not a full `https://...` URL, so it
can't fill in `VITE_API_URL` or `ALLOWED_ORIGINS` in the form our code
expects. Both are declared in `render.yaml` with `sync: false`, meaning
Render will prompt for them once at Blueprint creation and otherwise leave
them alone — so set them once, right after the first deploy:

1. **Backend → `ALLOWED_ORIGINS`**: after the frontend static site deploys,
   copy its URL (e.g. `https://school-scheduler-frontend.onrender.com`) and
   set it as the backend's `ALLOWED_ORIGINS` env var (comma-separate multiple
   origins if needed). Redeploy the backend for it to take effect.
2. **Frontend → `VITE_API_URL`**: after the backend deploys, copy its URL
   (e.g. `https://school-scheduler-backend.onrender.com`) and set it as the
   frontend's `VITE_API_URL` env var. Vite inlines this at **build time**, so
   you must trigger a manual redeploy of the frontend afterwards — just
   saving the env var does not update the already-built `dist/` output.

Until both of these are set, the deployed frontend won't be able to reach
the backend (CORS will reject the request), even though both services are
individually "live".

## Free-tier limitations

Both services are configured with `plan: free`. On Render's free tier:

- Services **spin down after 15 minutes of inactivity**.
- The next request after that wakes the service back up, which takes
  **up to ~1 minute** (cold start) before it responds — the CP-SAT solver
  runs on top of that, so the very first schedule generation after a period
  of inactivity can feel slow. Subsequent requests are normal speed until it
  sleeps again.
- This is fine for demos/evaluation; for production use with real users,
  upgrade both services off the free plan to avoid the sleep/cold-start
  behavior.

### Solver performance on free-tier CPU

Render's free-tier instances give the container a single CPU core (its own
logs show `Setting WEB_CONCURRENCY=1 by default, based on available CPUs`).
CP-SAT's parallel search doesn't help — and actively hurts — on a single
core, since the extra search workers just add thread-scheduling overhead
for threads that can never run concurrently. `render.yaml` tunes for this:

- `SOLVER_WORKERS=1` (backend `SOLVER_WORKERS` env var, read in
  `app/solver/scheduler.py`) — disables CP-SAT's multi-threaded search.
  Locally this defaults to 4 for faster iteration on a multi-core dev
  machine.
- `SOLVER_TIME_LIMIT_SECONDS=200` (backend env var, read in `app/main.py`)
  — gives the solver much more wall-clock time than the ~1.3s the full real
  dataset (2242 slots) took locally. A single weak core needs a lot more
  time than that local, multi-core estimate suggests. Locally this defaults
  to 30s for fast iteration.

**If the full real dataset still doesn't solve within a few minutes on
Render's free tier even with these settings**, the honest conclusion is
that free-tier compute is insufficient for this problem size. In that case,
either:

- Run the demo against a smaller subset of the data (e.g. filter the
  workload file down to fewer classes) so the deployed site stays
  responsive as a UI demo, or
- Tell the school administrator to run the full pipeline locally via
  `docker-compose up` for real use, treating the deployed Render site as a
  UI/workflow demo on lighter datasets rather than the production tool for
  the real schedule.
