"""Business-logic package for the Student Report Generator.

This package is framework-agnostic — it does not import Flask, request, or any
web-related symbol. The same logic can be invoked from a Flask handler, a CLI
script, a Celery task, or any future REST API without modification.
"""
from .calculations import compute_percentage, compute_total
from .grading import assign_grade
from .models import SUBJECTS, StudentInput, StudentReport
from .pdf_generator import generate_pdf

__all__ = [
    "SUBJECTS",
    "StudentInput",
    "StudentReport",
    "assign_grade",
    "compute_percentage",
    "compute_total",
    "generate_pdf",
]
