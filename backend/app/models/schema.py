from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class Teacher(BaseModel):
    """Represents an individual teacher in the school.

    Corresponds to:
    - Instructors identified in the Teacher Workload spreadsheet (`Нагрузка.xlsx`).
    """

    id: str = Field(..., description="Slugified unique teacher ID, e.g. 'inshakova-oa'")
    full_name: str = Field(..., description="Full teacher name with initials, e.g. 'Иншакова О.А.'")
    subjects: List[str] = Field(
        default_factory=list,
        description="List of subject names this teacher is qualified to teach, e.g. ['русский язык', 'литература']",
    )


class ClassGroup(BaseModel):
    """Represents a specific school class cohort/section.

    Corresponds to:
    - Specific class identifiers across curriculum plans and workload tables (e.g., '5А', '11Б').
    """

    name: str = Field(..., description="The raw class identifier as used in source documents, e.g. '5А', '11Б'")


class CurriculumRequirement(BaseModel):
    """Represents the academic workload required for a given grade and subject.

    Corresponds to:
    - Federal and school curriculum documents (`УП_*.docx` - Учебный план).

    Notes on fields:
    - `grade`: Parallel/grade level (1-11). In Russian schools, curriculum guidelines
      are defined at the grade-level standard rather than per individual class letter.
    - `hours_per_week`: Stored as a float because Russian curriculum allocations can be fractional
      (e.g., 0.5 hours/week for subjects conducted every other week or split across terms).
    - `track`: Specialized educational profile (e.g. 'Математическая вертикаль',
      'Естественно-научная вертикаль', 'Гуманитарный профиль') typically applicable for grades 7-11.
      None for general education / non-specialized tracks.
    """

    grade: int = Field(..., ge=1, le=11, description="Grade parallel level (1-11)")
    subject: str = Field(..., description="Standardized subject name (e.g. 'Алгебра', 'Русский язык')")
    hours_per_week: float = Field(..., ge=0.0, description="Weekly hours allocated (can be fractional, e.g. 0.5)")
    track: Optional[str] = Field(
        default=None,
        description="Specialized academic track/profile (e.g. 'Математическая вертикаль'), or None for standard curriculum",
    )


class Assignment(BaseModel):
    """Represents a specific teaching assignment mapping a teacher to a class.

    Corresponds to:
    - Rows in the teacher workload spreadsheet (`Нагрузка.xlsx` / Тарификация).

    Notes on fields:
    - `class_name`: References a specific class cohort (e.g., '5А'), unlike `CurriculumRequirement.grade`.
    - `hours_per_week`: Teaching hours per week allocated to this teacher for this class and subject.
    - `group`: Subgroup identifier (e.g. '1', '2', '3') when a class is split for a subject
      (e.g., foreign language, computer science, technology, or profile electives). None means whole class.
    """

    teacher_id: str = Field(..., description="Teacher ID assigned to teach this subject")
    subject: str = Field(..., description="Subject name being taught")
    class_name: str = Field(..., description="Target class name, e.g. '5А'")
    hours_per_week: float = Field(..., ge=0.0, description="Weekly hours assigned to this teacher for this class")
    group: Optional[str] = Field(
        default=None,
        description="Subgroup identifier (e.g. '1', '2') when class is split, or None for whole class",
    )


class ScheduleSlot(BaseModel):
    """Represents one scheduled lesson entry in the master timetable grid.

    Corresponds to:
    - An assigned period cell in the generated school schedule.

    Notes on fields:
    - `day`: Day of the week in Russian.
    - `period`: Lesson period number (1 to 9).
    - `group`: Subgroup indicator (e.g. '1' or '2') when classes are divided for languages,
      computer science, or technology labs. None if the full class attends together.
    - `room`: Optional assigned classroom or laboratory room code.
    """

    day: Literal["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"] = Field(
        ..., description="Day of the week"
    )
    period: int = Field(..., ge=1, le=9, description="Lesson period index (1 to 9)")
    teacher_id: str = Field(..., description="Identifier of the teacher conducting the lesson")
    class_name: str = Field(..., description="Target class name, e.g. '5А'")
    subject: str = Field(..., description="Subject being taught")
    group: Optional[str] = Field(
        default=None,
        description="Subgroup identifier (e.g. '1', '2') when class is split, or None for whole class",
    )
    room: Optional[str] = Field(default=None, description="Assigned room identifier or number")


class ValidationIssue(BaseModel):
    """Represents a validation warning or error discovered during document parsing or scheduling.

    Notes on fields:
    - `severity`: Either 'error' (prevents generation) or 'warning' (discrepancy to report).
    - `context`: Free-form dictionary containing contextual diagnostic details
      (e.g., `{'class': '5А', 'subject': 'русский язык', 'expected_hours': 5, 'actual_hours': 4}`).
    """

    severity: Literal["error", "warning"] = Field(..., description="Severity level of the issue")
    message: str = Field(..., description="Human-readable explanation of the validation issue")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata providing additional diagnostic context",
    )


class ParsedSchoolData(BaseModel):
    """Unified intermediate representation aggregated from all ingested source files.

    Corresponds to:
    - Combined data parsed from `УП_*.docx` (curriculum) and `Нагрузка.xlsx` (workload).
    """

    teachers: List[Teacher] = Field(default_factory=list, description="All parsed teachers")
    classes: List[ClassGroup] = Field(default_factory=list, description="All parsed class groups")
    curriculum: List[CurriculumRequirement] = Field(
        default_factory=list, description="All parsed grade-level curriculum requirements"
    )
    assignments: List[Assignment] = Field(
        default_factory=list, description="All parsed teacher-to-class workload assignments"
    )


class GenerateScheduleResponse(BaseModel):
    """Response payload containing generated timetable slots and any validation warnings."""

    schedule: List[ScheduleSlot] = Field(default_factory=list, description="Generated timetable lesson slots")
    warnings: List[ValidationIssue] = Field(
        default_factory=list, description="Validation issues, soft constraint warnings, or discrepancies"
    )
