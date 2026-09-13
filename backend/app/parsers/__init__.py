"""Parsers for curriculum documents (.docx) and teacher workload spreadsheets (.xlsx)."""

from .curriculum_parser import parse_curriculum_docx
from .workload_parser import parse_workload_xlsx

__all__ = ["parse_curriculum_docx", "parse_workload_xlsx"]
