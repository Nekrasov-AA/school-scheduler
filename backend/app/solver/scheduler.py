"""School timetable generation solver using Google OR-Tools CP-SAT.

Formulates timetable generation as a Constraint Satisfaction Problem (CSP):
- Grid: 5 days (Понедельник - Пятница), periods 1 to 9 (45 total slots per week).
- Hard Constraint 1: A teacher can teach at most one class in a given (day, period) slot.
- Hard Constraint 2: A class can attend at most one subject in a given (day, period) slot.
- Hard Constraint 3: The total number of scheduled slots for each assignment must equal its required hours.
"""

import logging
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Literal, Optional, Tuple

from ortools.sat.python import cp_model

from app.models.schema import Assignment, ScheduleSlot

logger = logging.getLogger(__name__)

DAYS: List[Literal["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]] = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
]
PERIODS: List[int] = list(range(1, 10))  # 1 to 9 (45 total periods in week)


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


def generate_schedule(
    assignments: List[Assignment],
    time_limit_seconds: int = 60,
    num_search_workers: int = 8,
) -> Tuple[List[ScheduleSlot], SolverStatus]:
    """Generates an optimal or feasible school timetable satisfying all hard constraints.

    Args:
        assignments: List of teacher-class-subject workload assignments.
        time_limit_seconds: Maximum solve time in seconds.
        num_search_workers: Number of parallel search workers for CP-SAT.

    Returns:
        (schedule_slots, solver_status) tuple.
    """
    if not assignments:
        return [], SolverStatus.OPTIMAL

    model = cp_model.CpModel()

    # Decision variables: x[assignment_idx, day, period] in {0, 1}
    # x[(a_idx, d, p)] == 1 iff assignment a_idx is scheduled on day d, period p.
    x: Dict[Tuple[int, str, int], cp_model.IntVar] = {}

    for a_idx, assignment in enumerate(assignments):
        req_hours = int(round(assignment.hours_per_week))
        if req_hours <= 0:
            continue

        for day in DAYS:
            for period in PERIODS:
                var_name = f"x_a{a_idx}_{day}_{period}"
                x[(a_idx, day, period)] = model.NewBoolVar(var_name)

        # Constraint 3: Each assignment must be scheduled for exactly its required hours
        model.Add(
            sum(x[(a_idx, day, period)] for day in DAYS for period in PERIODS) == req_hours
        )

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
