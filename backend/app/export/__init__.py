"""Export package for converting generated school schedules into document formats."""

from .docx_exporter import export_schedule_to_docx

__all__ = ["export_schedule_to_docx"]
