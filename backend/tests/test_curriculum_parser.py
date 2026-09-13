import os
from collections import defaultdict
from typing import Dict, List, Set

import pytest

from app.models.schema import CurriculumRequirement
from app.parsers.curriculum_parser import (
    extract_grade11_class_track_mapping,
    parse_curriculum_docx,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def format_grade_summary(requirements: List[CurriculumRequirement]) -> str:
    """Helper to group requirements by grade and format diagnostic summary."""
    grade_map: Dict[int, List[CurriculumRequirement]] = defaultdict(list)
    for req in requirements:
        grade_map[req.grade].append(req)

    lines = []
    for grade in sorted(grade_map.keys()):
        reqs = grade_map[grade]
        unique_subjects: Set[str] = {r.subject for r in reqs}
        tracks: Set[str] = {r.track for r in reqs if r.track}
        warning = " ⚠️ WARNING: Suspiciously few subjects (< 3)!" if len(unique_subjects) < 3 else ""

        lines.append(f"  Grade {grade:2d}: {len(reqs)} entries ({len(unique_subjects)} unique subjects, tracks: {len(tracks)}){warning}")
        for r in reqs:
            track_str = f" [track: {r.track}]" if r.track else ""
            lines.append(f"    - {r.subject}: {r.hours_per_week} hrs/week{track_str}")

    return "\n".join(lines)


def test_parse_up_noo():
    """Test parsing Primary Education curriculum plan (Grades 1-4)."""
    file_path = os.path.join(FIXTURES_DIR, "up_noo.docx")
    assert os.path.exists(file_path), f"Fixture not found: {file_path}"

    results = parse_curriculum_docx(file_path)
    print(f"\n==================== УП НОО (Grades 1-4) ====================")
    print(f"Total parsed entries: {len(results)}")
    print(format_grade_summary(results))

    assert len(results) > 0, "Expected at least 1 parsed requirement from up_noo.docx"

    # Check that grades are strictly within 1-4
    grades = {r.grade for r in results}
    assert grades.issubset({1, 2, 3, 4})
    # Every grade in 1-4 should have multiple subjects
    for g in [1, 2, 3, 4]:
        count = sum(1 for r in results if r.grade == g)
        assert count >= 3, f"Grade {g} has suspiciously few entries: {count}"


def test_parse_up_ooo():
    """Test parsing Basic General Education curriculum plan (Grades 5-9)."""
    file_path = os.path.join(FIXTURES_DIR, "up_ooo.docx")
    assert os.path.exists(file_path), f"Fixture not found: {file_path}"

    results = parse_curriculum_docx(file_path)
    print(f"\n==================== УП ООО (Grades 5-9) ====================")
    print(f"Total parsed entries: {len(results)}")
    print(format_grade_summary(results))

    assert len(results) > 0, "Expected at least 1 parsed requirement from up_ooo.docx"

    # Check grades are within 5-9
    grades = {r.grade for r in results}
    assert grades.issubset({5, 6, 7, 8, 9})

    # Check track detection for grades 7-9
    tracks = {r.track for r in results if r.track}
    print(f"\nDetected distinct tracks in УП ООО: {tracks}")
    assert any("Математическая вертикаль" in t for t in tracks)
    assert any("Естественно-научная вертикаль" in t for t in tracks)

    for g in [5, 6, 7, 8, 9]:
        count = sum(1 for r in results if r.grade == g)
        assert count >= 3, f"Grade {g} has suspiciously few entries: {count}"


def test_parse_up_soo():
    """Test parsing Senior Secondary Education curriculum plan (Grades 10-11)."""
    file_path = os.path.join(FIXTURES_DIR, "up_soo.docx")
    assert os.path.exists(file_path), f"Fixture not found: {file_path}"

    results = parse_curriculum_docx(file_path)
    print(f"\n==================== УП СОО (Grades 10-11) ====================")
    print(f"Total parsed entries: {len(results)}")
    print(format_grade_summary(results))

    assert len(results) > 0, "Expected at least 1 parsed requirement from up_soo.docx"

    # Check grades are within 10-11
    grades = {r.grade for r in results}
    assert grades.issubset({10, 11})

    # Check track detection for Grades 10-11
    tracks = {r.track for r in results if r.track}
    print(f"\nDetected distinct tracks in УП СОО: {tracks}")
    assert len(tracks) >= 3, f"Expected multiple profile tracks, found: {tracks}"

    # Check class letter to track mapping for grade 11
    class_map = extract_grade11_class_track_mapping(file_path)
    print(f"\nGrade 11 class-to-track mapping: {class_map}")
    assert len(class_map) > 0, "Expected class-to-track mapping for Grade 11"

    for g in [10, 11]:
        count = sum(1 for r in results if r.grade == g)
        assert count >= 3, f"Grade {g} has suspiciously few entries: {count}"
