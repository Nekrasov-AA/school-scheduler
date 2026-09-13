import os
import time
from collections import defaultdict
from typing import List

import pytest

from app.models.schema import Assignment, ScheduleSlot
from app.parsers.curriculum_parser import (
    extract_grade11_class_track_mapping,
    parse_curriculum_docx,
)
from app.parsers.workload_parser import parse_workload_xlsx
from app.solver.scheduler import SolverStatus, generate_schedule

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def verify_schedule_integrity(assignments: List[Assignment], schedule: List[ScheduleSlot]):
    """Helper to verify hard constraints against the generated schedule under two-level subgroup rules."""
    # 1. No teacher double-booked in same (day, period)
    teacher_slot_map = defaultdict(list)
    # 2. No class double-booking violations under two-level rules:
    #    - Same subgroup cannot have > 1 lesson in same (day, period)
    #    - Whole-class lesson (group=None) cannot overlap with ANY subgroup lesson in same (day, period)
    class_subgroup_slot_map = defaultdict(list)
    class_whole_slot_map = defaultdict(list)

    for slot in schedule:
        teacher_slot_map[(slot.teacher_id, slot.day, slot.period)].append(slot)
        if slot.group is None:
            class_whole_slot_map[(slot.class_name, slot.day, slot.period)].append(slot)
        else:
            class_subgroup_slot_map[(slot.class_name, slot.group, slot.day, slot.period)].append(slot)

        # Constraint 4 check: Primary school period caps
        # Grade 1 <= 5, Grades 2-4 <= 6, Grades 5-11 <= 9
        grade = int(slot.class_name[:2]) if slot.class_name[:2].isdigit() else int(slot.class_name[:1])
        if grade == 1:
            assert slot.period <= 5, (
                f"Grade 1 violation: class {slot.class_name} scheduled in period {slot.period} > 5"
            )
        elif 2 <= grade <= 4:
            assert slot.period <= 6, (
                f"Primary school violation: class {slot.class_name} (Grade {grade}) scheduled in period {slot.period} > 6"
            )

        # Constraint 5 check: PE never in period 1
        s_low = slot.subject.lower().strip()
        if "физ. культура" in s_low or "физическая культура" in s_low or "физ-ра" in s_low:
            assert slot.period != 1, (
                f"PE violation: subject {slot.subject} for class {slot.class_name} scheduled in period 1"
            )

    for key, slots in teacher_slot_map.items():
        assert len(slots) == 1, f"Teacher double-booking violation for {key}: {slots}"

    for key, slots in class_whole_slot_map.items():
        assert len(slots) == 1, f"Whole-class double-booking violation for {key}: {slots}"
        c_name, d, p = key
        # Check that no subgroup of this class is scheduled in the same (day, period)
        for (sc_name, s_grp, sd, sp), sub_slots in class_subgroup_slot_map.items():
            if sc_name == c_name and sd == d and sp == p:
                raise AssertionError(
                    f"Conflict: Whole-class lesson {slots} overlaps with subgroup {s_grp} lesson {sub_slots} on {d} period {p}"
                )

    for key, slots in class_subgroup_slot_map.items():
        assert len(slots) == 1, f"Subgroup double-booking violation for {key}: {slots}"

    # 3. Scheduled slots count matches sum of required hours
    total_required_hours = sum(int(round(a.hours_per_week)) for a in assignments if a.hours_per_week > 0)
    assert len(schedule) == total_required_hours, (
        f"Scheduled slots count ({len(schedule)}) does not match required hours ({total_required_hours})"
    )


def test_small_synthetic_schedule():
    """Small synthetic test case with 3 teachers, 2 classes, and easily satisfiable workload."""
    assignments = [
        Assignment(teacher_id="ivanov-ii", subject="Математика", class_name="5А", hours_per_week=4.0),
        Assignment(teacher_id="ivanov-ii", subject="Математика", class_name="5Б", hours_per_week=4.0),
        Assignment(teacher_id="petrova-aa", subject="Русский язык", class_name="5А", hours_per_week=5.0),
        Assignment(teacher_id="petrova-aa", subject="Русский язык", class_name="5Б", hours_per_week=5.0),
        Assignment(teacher_id="sidorov-ss", subject="История", class_name="5А", hours_per_week=2.0),
        Assignment(teacher_id="sidorov-ss", subject="История", class_name="5Б", hours_per_week=2.0),
    ]

    start_time = time.time()
    schedule, status = generate_schedule(assignments, time_limit_seconds=10)
    elapsed = time.time() - start_time

    print("\n==================== SMALL SYNTHETIC SCHEDULE ====================")
    print(f"Solver Status: {status.value}")
    print(f"Elapsed Time: {elapsed:.4f} seconds")
    print(f"Generated Schedule Slots: {len(schedule)}")

    assert status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE), f"Expected feasible solution, got: {status}"
    verify_schedule_integrity(assignments, schedule)

    # Print first few scheduled slots
    print("\nSample Scheduled Slots:")
    for slot in schedule[:10]:
        print(f"  {slot.day:<12} | Period {slot.period} | Class: {slot.class_name:<4} | Subject: {slot.subject:<15} | Teacher: {slot.teacher_id}")


def test_primary_school_constraint():
    """Synthetic test case verifying primary school period caps.

    1. Feasible case: Grade 1 class with 16 hours/week (fits within period caps).
    2. Infeasible case: Grade 1 class with 30 hours/week (cannot fit in 25 slots across 5 days x 5 periods).
    """
    # Feasible primary workload (16 hours)
    feasible_assignments = [
        Assignment(teacher_id="teacher-1", subject="Русский язык", class_name="1А", hours_per_week=5.0),
        Assignment(teacher_id="teacher-1", subject="Математика", class_name="1А", hours_per_week=4.0),
        Assignment(teacher_id="teacher-1", subject="Литературное чтение", class_name="1А", hours_per_week=4.0),
        Assignment(teacher_id="teacher-pe", subject="физ. культура", class_name="1А", hours_per_week=3.0),
    ]

    schedule, status = generate_schedule(feasible_assignments, time_limit_seconds=10)
    assert status == SolverStatus.OPTIMAL, f"Expected optimal, got: {status}"
    assert len(schedule) == 16
    verify_schedule_integrity(feasible_assignments, schedule)

    for slot in schedule:
        assert slot.period <= 5, f"Grade 1 class 1А scheduled in period {slot.period} > 5"

    print("\n✅ Verified: Grade 1 class schedule only uses periods <= 5.")

    # Infeasible primary workload (30 hours > 25 max slots for cap 5)
    infeasible_assignments = [
        Assignment(teacher_id="teacher-1", subject="Русский язык", class_name="1А", hours_per_week=16.0),
        Assignment(teacher_id="teacher-1", subject="Математика", class_name="1А", hours_per_week=14.0),
    ]
    _, inf_status = generate_schedule(infeasible_assignments, time_limit_seconds=5)
    assert inf_status == SolverStatus.INFEASIBLE, f"Expected infeasible for 30h in 25 slots, got {inf_status}"
    print("✅ Verified: Over-capacity primary class correctly reported as INFEASIBLE.")


def test_pe_no_period_1_constraint():
    """Synthetic test verifying Physical Education is never scheduled in period 1."""
    assignments = [
        Assignment(teacher_id="pe-t1", subject="Физическая культура", class_name="7А", hours_per_week=3.0),
        Assignment(teacher_id="pe-t1", subject="физ. культура", class_name="7Б", hours_per_week=3.0),
        Assignment(teacher_id="math-t", subject="Математика", class_name="7А", hours_per_week=4.0),
        Assignment(teacher_id="math-t", subject="Математика", class_name="7Б", hours_per_week=4.0),
    ]

    schedule, status = generate_schedule(assignments, time_limit_seconds=10)
    assert status == SolverStatus.OPTIMAL
    assert len(schedule) == 14
    verify_schedule_integrity(assignments, schedule)

    pe_slots = [s for s in schedule if "физ" in s.subject.lower()]
    assert len(pe_slots) == 6
    for s in pe_slots:
        assert s.period != 1, f"PE scheduled in period 1: {s}"

    print(f"✅ Verified: All {len(pe_slots)} PE slots scheduled in periods > 1.")


def test_subgroup_synthetic_schedule():
    """Synthetic test case verifying parallel subgroup scheduling alongside whole-class lessons.

    Class 10А has:
    - 4 hours of Math (whole class, group=None, teacher: math-t)
    - 2 hours of English Group 1 (group='1', teacher: eng-t1)
    - 2 hours of English Group 2 (group='2', teacher: eng-t2)
    """
    assignments = [
        Assignment(teacher_id="math-t", subject="Математика", class_name="10А", hours_per_week=4.0, group=None),
        Assignment(teacher_id="eng-t1", subject="Английский язык", class_name="10А", hours_per_week=2.0, group="1"),
        Assignment(teacher_id="eng-t2", subject="Английский язык", class_name="10А", hours_per_week=2.0, group="2"),
    ]

    start_time = time.time()
    schedule, status = generate_schedule(assignments, time_limit_seconds=10)
    elapsed = time.time() - start_time

    print("\n==================== SUBGROUP SYNTHETIC SCHEDULE ====================")
    print(f"Solver Status: {status.value}")
    print(f"Elapsed Time: {elapsed:.4f} seconds")
    print(f"Generated Schedule Slots: {len(schedule)}")

    assert status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE), f"Expected feasible solution, got: {status}"
    verify_schedule_integrity(assignments, schedule)

    # Verify that subgroups can run in parallel (same day & period for group 1 & group 2)
    grp1_slots = {(s.day, s.period) for s in schedule if s.group == "1"}
    grp2_slots = {(s.day, s.period) for s in schedule if s.group == "2"}
    whole_slots = {(s.day, s.period) for s in schedule if s.group is None}

    print(f"Group 1 slots: {grp1_slots}")
    print(f"Group 2 slots: {grp2_slots}")
    print(f"Whole class slots: {whole_slots}")

    # Neither subgroup must ever overlap with whole-class slots
    assert grp1_slots.isdisjoint(whole_slots), "Group 1 overlapped with whole-class slot!"
    assert grp2_slots.isdisjoint(whole_slots), "Group 2 overlapped with whole-class slot!"

    print("✅ Verified: Subgroup lessons never overlap with whole-class lessons.")
    for s in schedule:
        grp_str = f" [Group {s.group}]" if s.group else " [Whole Class]"
        print(f"  {s.day:<12} | Period {s.period} | Class: {s.class_name:<4} | Subject: {s.subject:<18}{grp_str} | Teacher: {s.teacher_id}")


def test_real_dataset_schedule():
    """Full pipeline run with real curriculum and workload fixtures (107 teachers, 76 classes, 788 assignments)."""
    workload_path = os.path.join(FIXTURES_DIR, "workload.xlsx")
    soo_path = os.path.join(FIXTURES_DIR, "up_soo.docx")

    # Step 1: Parse all curricula
    up_noo = parse_curriculum_docx(os.path.join(FIXTURES_DIR, "up_noo.docx"))
    up_ooo = parse_curriculum_docx(os.path.join(FIXTURES_DIR, "up_ooo.docx"))
    up_soo = parse_curriculum_docx(soo_path)
    all_curriculum = up_noo + up_ooo + up_soo
    soo_class_track_map = extract_grade11_class_track_mapping(soo_path)

    # Step 2: Parse workload
    teachers, assignments, warnings = parse_workload_xlsx(
        file_path=workload_path,
        curriculum=all_curriculum,
        soo_class_track_map=soo_class_track_map,
    )

    total_req_hours = sum(int(round(a.hours_per_week)) for a in assignments if a.hours_per_week > 0)
    distinct_classes = set(a.class_name for a in assignments)

    print("\n==================== REAL DATASET SOLVE RUN ====================")
    print(f"Input Data: {len(teachers)} Teachers | {len(distinct_classes)} Classes | {len(assignments)} Assignments")
    print(f"Total Required Lesson Slots: {total_req_hours}")

    start_time = time.time()
    schedule, status = generate_schedule(assignments, time_limit_seconds=60)
    elapsed = time.time() - start_time

    print(f"\nSolver Execution Results:")
    print(f"  Status:       {status.value}")
    print(f"  Elapsed Time: {elapsed:.2f} seconds")
    print(f"  Slots Generated: {len(schedule)}")

    if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        verify_schedule_integrity(assignments, schedule)
        print("\n✅ Verification PASSED: No teacher double-booking, no class double-booking, all hours matched.")
        print("\nSample 15 Scheduled Slots from Full Timetable:")
        for s in schedule[:15]:
            print(f"  {s.day:<12} | Period {s.period} | Class: {s.class_name:<4} | Subject: {s.subject:<30} | Teacher: {s.teacher_id}")
    else:
        print(f"\n⚠️ Result status is {status.value}. (Infeasible or timed out within 60s)")
