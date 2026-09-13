"""Core data models and schemas for School Scheduler."""

from .schema import (
    Assignment,
    ClassGroup,
    CurriculumRequirement,
    GenerateScheduleResponse,
    ParsedSchoolData,
    ScheduleSlot,
    Teacher,
    ValidationIssue,
)

__all__ = [
    "Assignment",
    "ClassGroup",
    "CurriculumRequirement",
    "GenerateScheduleResponse",
    "ParsedSchoolData",
    "ScheduleSlot",
    "Teacher",
    "ValidationIssue",
]
