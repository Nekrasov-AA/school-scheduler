"""School timetable generation solver using Google OR-Tools CP-SAT.

Formulates timetable generation as a Constraint Satisfaction Problem (CSP):
- Grid: 5 days (Понедельник - Пятница), periods 1 to 9 (45 total slots per week).
- Hard Constraint 1: A teacher can teach at most one class in a given (day, period) slot.
- Hard Constraint 2: A class can attend at most one subject in a given (day, period) slot.
- Hard Constraint 3: The total number of scheduled slots for each assignment must equal its required hours.
"""

import logging
import os
import re
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from ortools.sat.python import cp_model

from app.models.schema import Assignment, ScheduleSlot

logger = logging.getLogger(__name__)

# SOLVER_WORKERS: number of parallel CP-SAT search workers. Defaults to 4 for
# local/multi-core dev. On a constrained single-core host (e.g. Render's free
# tier), requesting multiple workers adds thread-scheduling overhead for
# threads that can't actually run in parallel, so set this to 1 there.
DEFAULT_SOLVER_WORKERS = int(os.getenv("SOLVER_WORKERS", "4"))

DAYS: List[Literal["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]] = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
]
PERIODS: List[int] = list(range(1, 10))  # 1 to 9 (45 total periods in week)

# -----------------------------------------------------------------------------
# Maximum period caps per grade level (Constraint 4).
#
# PLACEHOLDER pending confirmation from school administration (see docs/OPEN_QUESTIONS.md, Question #1):
# - Grade 1 workload has 21-22 hrs/week, requiring up to period 5 on 1-2 days per week (cap: 5).
# - Grades 2-4 workload has 25-26 hrs/week, with shared specialist teachers (PE, Music, English),
#   requiring periods 1-6 (cap: 6) to accommodate non-overlapping teacher schedules.
# - Grades 5-11 use the full standard daily schedule up to period 9.
# -----------------------------------------------------------------------------
GRADE_PERIOD_CAPS: Dict[Any, int] = {
    1: 5,                  # Grade 1 (21-22 hrs/week -> up to period 5)
    "default_primary": 6,  # Grades 2-4 (25-26 hrs/week + specialist teachers -> up to period 6)
    "default_secondary": 9,# Grades 5-11 (standard periods 1-9)
}


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


def get_grade_from_class_name(class_name: str) -> int:
    """Extract grade level (1-11) from raw class identifier (e.g. '1А' -> 1, '11Б' -> 11)."""
    m = re.match(r"^(\d+)", class_name.strip())
    if not m:
        raise ValueError(f"Cannot extract grade level from class name '{class_name}'")
    return int(m.group(1))


def is_pe_subject(subject: str) -> bool:
    """Check if subject corresponds to Physical Education (Физическая культура / физ. культура / etc.)."""
    s = subject.lower().strip()
    return "физическая культура" in s or "физ. культура" in s or "физ-ра" in s or s == "физкультура"


def generate_schedule(
    assignments: List[Assignment],
    time_limit_seconds: int = 60,
    num_search_workers: int = DEFAULT_SOLVER_WORKERS,
    grade_period_caps: Optional[Dict[Any, int]] = None,
) -> Tuple[List[ScheduleSlot], SolverStatus]:
    """Generates an optimal or feasible school timetable satisfying all hard constraints:
    - Hard Constraint 1: A teacher can teach at most one class in a given (day, period) slot.
    - Hard Constraint 2: A class can attend at most one lesson per (day, period), with parallel subgroup support.
    - Hard Constraint 3: The total number of scheduled slots for each assignment must equal its required hours.
    - Hard Constraint 4: Grade period caps (primary grades restricted to early periods, e.g. 1-5 or 1-6).
    - Hard Constraint 5: Physical Education (Физическая культура) is NEVER scheduled in period 1.

    Args:
        assignments: List of teacher-class-subject workload assignments.
        time_limit_seconds: Maximum solve time in seconds.
        num_search_workers: Number of parallel search workers for CP-SAT. Defaults to
            DEFAULT_SOLVER_WORKERS (env var SOLVER_WORKERS, default 4).
        grade_period_caps: Optional override for grade period limits (defaults to GRADE_PERIOD_CAPS).

    Returns:
        (schedule_slots, solver_status) tuple.
    """
    if not assignments:
        return [], SolverStatus.OPTIMAL

    caps = grade_period_caps or GRADE_PERIOD_CAPS
    model = cp_model.CpModel()

    # Decision variables: x[assignment_idx, day, period] in {0, 1}
    # x[(a_idx, d, p)] == 1 iff assignment a_idx is scheduled on day d, period p.
    x: Dict[Tuple[int, str, int], cp_model.IntVar] = {}

    for a_idx, assignment in enumerate(assignments):
        req_hours = int(round(assignment.hours_per_week))
        if req_hours <= 0:
            continue

        grade = get_grade_from_class_name(assignment.class_name)
        if grade == 1:
            max_period = caps.get(1, 5)
        elif 2 <= grade <= 4:
            max_period = caps.get(grade, caps.get("default_primary", 6))
        else:
            max_period = caps.get(grade, caps.get("default_secondary", 9))

        is_pe = is_pe_subject(assignment.subject)

        # Determine candidate periods for this assignment:
        # - Primary school classes capped by max_period (e.g. 5 for Grade 1, 6 for Grades 2-4)
        # - Physical Education (PE) is never allowed in period 1
        allowed_periods = []
        for period in PERIODS:
            if period > max_period:
                continue
            if is_pe and period == 1:
                continue
            allowed_periods.append(period)

        for day in DAYS:
            for period in allowed_periods:
                var_name = f"x_a{a_idx}_{day}_{period}"
                x[(a_idx, day, period)] = model.NewBoolVar(var_name)

        # Constraint 3: Each assignment must be scheduled for exactly its required hours
        assigned_vars = [
            x[(a_idx, day, period)]
            for day in DAYS
            for period in allowed_periods
        ]
        model.Add(sum(assigned_vars) == req_hours)

    # Constraint 1: A teacher can teach at most one lesson per (day, period)
    # Group assignments by teacher_id
    teacher_assignments: Dict[str, List[int]] = {}
    for a_idx, assignment in enumerate(assignments):
        teacher_assignments.setdefault(assignment.teacher_id, []).append(a_idx)

    for teacher_id, a_indices in teacher_assignments.items():
        for day in DAYS:
            for period in PERIODS:
                active_vars = [
                    x[(a_idx, day, period)]
                    for a_idx in a_indices
                    if (a_idx, day, period) in x
                ]
                if len(active_vars) > 1:
                    model.Add(sum(active_vars) <= 1)

    # Constraint 2: Class conflict constraints (Two-level subgroup logic)
    # -------------------------------------------------------------------------
    # Level 1 (Within same subgroup / whole class):
    #   - For any specific subgroup (group="1", "2", ...) or whole class (group=None),
    #     students in that group can attend at most one lesson per (day, period).
    # Level 2 (Across subgroups and whole class):
    #   - A "whole class" lesson (group=None) requires all students in the class,
    #     so it conflicts with EVERY subgroup lesson of the same class at that (day, period).
    #   - Two DIFFERENT subgroups of the same class (e.g. group "1" and group "2")
    #     DO NOT conflict with each other and can run in parallel (e.g. English group 1 and 2).
    # -------------------------------------------------------------------------
    class_group_assignments: Dict[str, Dict[Optional[str], List[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for a_idx, assignment in enumerate(assignments):
        class_group_assignments[assignment.class_name][assignment.group].append(a_idx)

    for class_name, groups_dict in class_group_assignments.items():
        whole_class_indices = groups_dict.get(None, [])
        subgroup_keys = [g for g in groups_dict.keys() if g is not None]

        for day in DAYS:
            for period in PERIODS:
                # (a) Whole-class lessons bucket (group=None): at most 1 lesson
                whole_vars = [
                    x[(a_idx, day, period)]
                    for a_idx in whole_class_indices
                    if (a_idx, day, period) in x
                ]
                if len(whole_vars) > 1:
                    model.Add(sum(whole_vars) <= 1)

                # (b) Within each individual subgroup: at most 1 lesson
                for g_key in subgroup_keys:
                    sub_vars = [
                        x[(a_idx, day, period)]
                        for a_idx in groups_dict[g_key]
                        if (a_idx, day, period) in x
                    ]
                    if len(sub_vars) > 1:
                        model.Add(sum(sub_vars) <= 1)

                    # (c) Cross-group conflict: whole class lesson conflicts with this subgroup
                    # sum(whole_class_lessons) + sum(subgroup_lessons) <= 1
                    if whole_vars and sub_vars:
                        model.Add(sum(whole_vars) + sum(sub_vars) <= 1)

    # Solver setup
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    solver.parameters.num_search_workers = num_search_workers
    solver.parameters.log_search_progress = False

    logger.info(
        "Starting CP-SAT solver with %d assignments, %d variables, time_limit=%ds",
        len(assignments),
        len(x),
        time_limit_seconds,
    )

    status_code = solver.Solve(model)

    if status_code == cp_model.OPTIMAL:
        status = SolverStatus.OPTIMAL
    elif status_code == cp_model.FEASIBLE:
        status = SolverStatus.FEASIBLE
    elif status_code == cp_model.INFEASIBLE:
        status = SolverStatus.INFEASIBLE
        logger.warning("Timetable CSP model is INFEASIBLE.")
        return [], status
    elif status_code == cp_model.MODEL_INVALID:
        status = SolverStatus.UNKNOWN
        logger.error("Timetable CSP model is INVALID.")
        return [], status
    else:
        # TIMEOUT with no feasible solution found yet
        status = SolverStatus.TIMEOUT
        logger.warning("Solver timed out without finding a feasible solution.")
        return [], status

    # Extract schedule slots from solution
    schedule: List[ScheduleSlot] = []
    for (a_idx, day, period), var in x.items():
        if solver.Value(var) == 1:
            a = assignments[a_idx]
            schedule.append(
                ScheduleSlot(
                    day=day,
                    period=period,
                    teacher_id=a.teacher_id,
                    class_name=a.class_name,
                    subject=a.subject,
                    group=a.group,
                    room=None,
                )
            )

    logger.info("Schedule solved successfully with status '%s': %d slots generated.", status.value, len(schedule))
    return schedule, status
