import os
from collections import defaultdict
from typing import List, Set

import pytest

from app.models.schema import Assignment, Teacher, ValidationIssue
from app.parsers.curriculum_parser import (
    extract_grade11_class_track_mapping,
    parse_curriculum_docx,
)
from app.parsers.workload_parser import parse_workload_xlsx

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_parse_workload_xlsx():
    """Test parsing the teacher workload spreadsheet (Нагрузка.xlsx) with curriculum resolution."""
    workload_path = os.path.join(FIXTURES_DIR, "workload.xlsx")
    assert os.path.exists(workload_path), f"Fixture not found: {workload_path}"

    # Load all curriculum fixtures
    up_noo = parse_curriculum_docx(os.path.join(FIXTURES_DIR, "up_noo.docx"))
    up_ooo = parse_curriculum_docx(os.path.join(FIXTURES_DIR, "up_ooo.docx"))
    soo_path = os.path.join(FIXTURES_DIR, "up_soo.docx")
    up_soo = parse_curriculum_docx(soo_path)
    all_curriculum = up_noo + up_ooo + up_soo
    soo_class_track_map = extract_grade11_class_track_mapping(soo_path)

    teachers, assignments, warnings = parse_workload_xlsx(
        file_path=workload_path,
        curriculum=all_curriculum,
        soo_class_track_map=soo_class_track_map,
    )

    print("\n==================== НАГРУЗКА (Workload Summary) ====================")
    print(f"Total Teachers parsed: {len(teachers)}")
    print(f"Total Assignments parsed: {len(assignments)}")
    print(f"Total Validation Issues (Warnings): {len(warnings)}")

    assert len(teachers) > 0, "Expected at least 1 parsed teacher"
    assert len(assignments) > 0, "Expected at least 1 parsed assignment"

    # 1. Multi-subject teachers metric
    multi_subject_teachers = [t for t in teachers if len(t.subjects) > 1]
    print(f"\nTeachers with >1 subjects in their subjects list: {len(multi_subject_teachers)} out of {len(teachers)}")

    # 2. Verify Иншакова О.А. class 5А produces 3 separate assignments
    inshakova_5a_assignments = [
        a for a in assignments if a.teacher_id == "inshakova-o-a" and a.class_name == "5А"
    ]
    print("\n=== Inshakova O.A. Class 5A Resolved Assignments ===")
    for a in inshakova_5a_assignments:
        print(f"  - Subject: {a.subject:<35} | Hours/week: {a.hours_per_week}")

    assert len(inshakova_5a_assignments) == 3, (
        f"Expected 3 distinct assignments for Inshakova 5A, found: {inshakova_5a_assignments}"
    )
    inshakova_subjects = {a.subject: a.hours_per_week for a in inshakova_5a_assignments}
    assert inshakova_subjects.get("Русский язык") == 5.0
    assert inshakova_subjects.get("Литература") == 3.0
    assert inshakova_subjects.get("Практикум по русскому языку") == 1.0

    # 3. Sample Assignments (First 20)
    print(f"\nSample Assignments (First 20 of {len(assignments)}):")
    for idx, a in enumerate(assignments[:20], 1):
        print(
            f"  {idx:2d}. Teacher: {a.teacher_id:<25} | Class: {a.class_name:<4} | "
            f"Subject: {a.subject:<35} | Hours/week: {a.hours_per_week}"
        )

    # 4. Vacancies check
    print("\n==================== Вакансии (Vacancies) ====================")
    vacancy_teachers = [t for t in teachers if t.full_name.lower().startswith("вакансия")]
    print(f"Total Vacancies found: {len(vacancy_teachers)}")

    teacher_assignments_map = defaultdict(list)
    for a in assignments:
        teacher_assignments_map[a.teacher_id].append(a)

    for vt in vacancy_teachers:
        v_ass = teacher_assignments_map[vt.id]
        total_hours = sum(a.hours_per_week for a in v_ass)
        print(f"\n  Vacancy: '{vt.full_name}' (ID: {vt.id})")
        print(f"    Subjects: {vt.subjects}")
        print(f"    Assigned classes ({len(v_ass)}, total {total_hours} hrs/week):")
        if v_ass:
            for a in v_ass:
                print(f"      - Class {a.class_name}: {a.hours_per_week} hrs/week ({a.subject})")
        else:
            print("      - [No numeric assignments found in grid]")

    assert len(vacancy_teachers) > 0, "Expected vacancy positions to be parsed as Teachers"

    # 5. Distinct classes found
    distinct_classes: Set[str] = {a.class_name for a in assignments}
    print(f"\n==================== Distinct Classes ({len(distinct_classes)}) ====================")
    print(f"Classes found across all assignments: {sorted(distinct_classes)}")
    assert len(distinct_classes) >= 50, f"Expected ~76 classes, found {len(distinct_classes)}"

    # 6. Detailed Validation Issues dump
    print(f"\n==================== Validation Issues Dump ({len(warnings)} Warnings) ====================")
    for idx, w in enumerate(warnings, 1):
        ctx = w.context
        print(
            f"{idx:2d}. [{w.severity.upper()}] Teacher: {ctx.get('teacher_name', '')} | "
            f"Class: {ctx.get('class_name', '')} (Grade {ctx.get('grade', '')}) | "
            f"Hours: {ctx.get('total_hours', '')} | Combos: {ctx.get('matching_combinations_count', 0)}"
        )
        print(f"    Message: {w.message}")
