# Student Report Generator (Python 3 + Flask + ReportLab)

## Overview

This project allows users to:

- Enter student details using a form
- Calculate total marks and percentage automatically
- Generate a formatted student report
- Export the report as a PDF file

This is a Python 3 server-side implementation of the Student Report Generator, refactored from the original vanilla JavaScript browser application. The refactor preserves **100% of the original functional behavior** — the same five subjects, the same percentage formula `(total / 500) * 100`, the same six-tier grade ladder, and the same PDF visual layout — while delivering measurable runtime performance improvements through C-implemented Python primitives, compiled Jinja2 templates, and in-memory PDF streaming.

---

## Features

- **Student data entry form** — Captures the student's name, roll number, and marks for five subjects: Maths, Science, English, History, and Computer.
- **Total and percentage calculation** — Computes the total marks across the five subjects and the percentage using the fixed formula `(total / 500) * 100`.
- **Automatic grade assignment** — Maps the computed percentage to a letter grade using a six-tier ladder: ≥90 → **A+**, ≥80 → **A**, ≥70 → **B**, ≥60 → **C**, ≥50 → **D**, otherwise **F**.
- **On-screen report card rendering** — Displays the student's name, roll number, a per-subject marks table, total, percentage, and assigned grade after the form is submitted.
- **PDF export** — Generates and downloads a single-page PDF report named `<studentName>_Report.pdf`, laid out with the title "Student Report Card" and five labelled data lines for name, roll, total, percentage, and grade.
- **Responsive UI** — The form, report card, and overall layout are styled with the original CSS and adapt cleanly to common viewport sizes.

---

## Technologies Used

- **Python 3.13** (recommended; minimum **3.10**)
- **Flask 3.1.3** — WSGI web framework providing routing, request handling, template rendering, and PDF streaming
- **ReportLab 4.5.1** — Pure-Python library used for server-side PDF generation
- **Jinja2** — Template engine bundled with Flask, used to render the form and report card view
- **pytest 9.0.3** — Testing framework powering the behavioural parity test suite

---

## Project Structure

```text
Student_Mngt/
├── app.py
├── report_generator/
│   ├── __init__.py
│   ├── models.py
│   ├── calculations.py
│   ├── grading.py
│   └── pdf_generator.py
├── templates/
│   └── index.html
├── static/
│   └── style.css
├── tests/
│   ├── __init__.py
│   ├── test_calculations.py
│   ├── test_grading.py
│   ├── test_pdf_generator.py
│   └── test_app.py
├── requirements.txt
├── pyproject.toml
├── .python-version
├── .gitignore
├── Readme.md
└── Student Report Generator Javascript Pdf.pdf
```

---

## Installation / Setup

```bash
# Clone the repository
git clone https://github.com/ajitblitzy/Student_Mngt.git
cd Student_Mngt

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate    # POSIX (macOS/Linux)
# .\.venv\Scripts\activate   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

---

## How to Run

Two equivalent ways to start the development server:

```bash
# Option 1: Run directly
python app.py

# Option 2: Run via Flask CLI
flask --app app run
```

Once the server is running, the application is available at **`http://127.0.0.1:5000/`**. Open the URL in a browser, fill in the student details and marks, then:

- Click **Generate Report** to compute the total, percentage, and grade and display the report card on the page.
- Click **Download PDF** to obtain the generated PDF report (file name `<studentName>_Report.pdf`).

Both buttons submit the same form to the server; there is no implicit client-side ordering between them — each click is a standalone, stateless request.

---

## Testing

Run the full pytest test suite:

```bash
pytest
```

The test suite verifies behavioural parity with the original JavaScript implementation across the F-001 through F-006 capabilities. It comprises four modules:

- `tests/test_calculations.py` — Validates the total accumulation and the `(total / 500) * 100` percentage formula across representative inputs (all-zero, all-max, mixed marks).
- `tests/test_grading.py` — Exercises every boundary of the six-tier grade ladder (e.g., `89.99 → "A"`, `90.0 → "A+"`, `49.99 → "F"`, `50.0 → "D"`, `0.0 → "F"`, `100.0 → "A+"`).
- `tests/test_pdf_generator.py` — Confirms the generated PDF begins with the `%PDF-` magic header, ends with `%%EOF`, and contains the title "Student Report Card" together with the rendered student fields.
- `tests/test_app.py` — Drives the Flask test client against the live routes `/`, `/generate`, and `/download`, asserting status codes, rendered HTML fragments, and `Content-Disposition` headers for the PDF download.

---

## Architecture Notes

The application uses a small, conventional layered architecture:

- **Application Factory pattern** — `app.py` exposes a `create_app()` function that constructs and configures the Flask application. This makes test fixtures and alternative entry points (e.g., a production WSGI server) trivial to wire up.
- **MVC-like separation** — `app.py` acts as the controller (request handling and routing); `templates/index.html` is the view (Jinja2-rendered HTML); the `report_generator/` package contains the model and service layer (typed data containers and business logic).
- **Single Responsibility Principle** — One module per concern: `calculations.py` for totals and percentages, `grading.py` for grade thresholds, `pdf_generator.py` for PDF rendering, and `models.py` for the data containers (`StudentInput`, `StudentReport`).
- **Stateless single-request model** — Both the on-screen report and the PDF download are produced from a single form submission per click; the server holds no session state and the two endpoints share no implicit ordering. This replaces the original DOM-as-transient-shared-state pattern of the JavaScript version.
- **PEP 484 type hints throughout** — Every public function in `report_generator/` is fully type-annotated, enabling static analysis and self-documenting code.

---

## Performance Improvements

The migration is not just a language port — each replacement is chosen for a measurable performance benefit over the original browser-side implementation:

- **C-implemented `sum()`** — `total = sum(marks.values())` runs in CPython's C accumulator and replaces the JavaScript `for...in` loop, eliminating per-iteration interpreter overhead.
- **Single-pass Jinja2 template rendering** — Replaces the O(n²) `tableBody.innerHTML += row` pattern (which rebuilt the DOM subtree on every append) with a compiled Jinja2 `{% for %}` loop that writes once into a single buffer.
- **In-memory `BytesIO` PDF buffer** — `ReportLab` writes the PDF entirely to memory and Flask's `send_file` streams the bytes to the client; no temporary disk files are created on the server.
- **Module-level precomputed constants** — `SUBJECTS` (the five subject names) and `GRADE_THRESHOLDS` (the six-tier ladder) are evaluated once at import time and reused on every request, replacing the JS pattern of reconstructing the `subjects` object on every click.
- **`@lru_cache` memoization on `assign_grade`** — Repeated grade lookups for the same percentage hit a small in-process cache instead of re-scanning the threshold table.
- **f-strings for fast interpolation** — Used throughout for filename construction (`f"{name}_Report.pdf"`) and PDF text drawing; compiled to bytecode that is faster than `str.format` or `%`-formatting.

---

## Future Enhancements

The following items remain proposed and are not part of the current refactor:

- Add database support
- Add multiple student report management
- Add charts and analytics
- Add teacher comments
- Add digital signature support
- Export reports to Excel

---

## Repository

The project source is hosted at **[github.com/ajitblitzy/Student_Mngt](https://github.com/ajitblitzy/Student_Mngt)**.

A historical reference PDF, `Student Report Generator Javascript Pdf.pdf`, is retained in the repository root as a snapshot of the prior JavaScript implementation. It is not used at runtime by the current Python application.
