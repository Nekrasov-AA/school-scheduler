"""Parsers for curriculum documents (.docx) and teacher workload spreadsheets (.xlsx)."""

from .curriculum_parser import parse_curriculum_docx

__all__ = ["parse_curriculum_docx"]
