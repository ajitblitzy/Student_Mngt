# Technical Specification

# 0. Agent Action Plan

## 0.1 Core Refactoring Objective

Based on the prompt, the Blitzy platform understands that the refactoring objective is to read the source code embedded in the PDF that ships in this repository, confirm that the source code was successfully read and analyzed, state which programming language the source code is written in, and produce a complete Python 3 rewrite of that source code that preserves every existing feature and behaviour unchanged.

The source code lives inside the file `Student Report Generator Javascript Pdf.pdf` (a 7-page PDF, 87,443 bytes) at the repository root. After reading the PDF and the mirrored copy of the same code held in `Readme.md`, the Blitzy platform has confirmed:

- The PDF is fully readable and the embedded source code is fully analyzable
- The programming language used in the PDF is **JavaScript** (browser-side ECMAScript using both ES5 syntax and a small set of ES6 features — `const` / `let`, template literals, and destructuring assignment), accompanied by HTML5 markup and CSS3 styling that together compose a static single-page client-side web application
- The single external library is jsPDF v2.5.1, loaded at runtime from `https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js`

The refactor will translate this stack to Python 3 while keeping all observable behaviour identical: the same input fields (student name, roll number, and five subject marks for Maths, Science, English, History, Computer), the same computed outputs (total marks, percentage as `(total / 500) × 100`, and a six-tier letter grade), the same on-screen report card rendering, and the same downloadable PDF report with the same content and the same filename pattern `{name}_Report.pdf`.

### 0.1.1 Refactoring Classification

| Dimension | Classification |
|-----------|----------------|
| Refactoring type | Tech stack migration (cross-language port) |
| Source runtime | Browser JavaScript engine (vanilla DOM, no build step) |
| Target runtime | Python 3 (CPython 3.12) |
| Target repository | Same repository (`/tmp/blitzy/Student_Mngt/15-May-26-Br2_c59dc0/`) |
| Behaviour preservation | Mandatory — explicit user rule `Ajit_Test_Refactor` |
| Build / compile step introduced | None; Python is interpreted and Flask serves directly |

### 0.1.2 Explicit Refactoring Goals

- Replace the JavaScript implementation of the report computation (`generateReport()` in the source `script.js`) with a Python implementation that yields the same total, percentage (two-decimal format), and letter grade for the same inputs
- Replace the jsPDF-driven client-side PDF export (`downloadPDF()`) with a server-side fpdf2 implementation that produces a PDF whose textual content and download filename match the original byte-for-byte at the text level (`Student Report Card` title; labelled lines for Student Name, Roll Number, Total Marks, Percentage, and Grade; filename `{name}_Report.pdf`)
- Preserve the HTML form (`studentName`, `rollNumber`, `maths`, `science`, `english`, `history`, `computer`) and the on-screen report card anchors (`rName`, `rRoll`, `marksTable`, `totalMarks`, `percentage`, `grade`) so the user-facing page is visually and structurally identical
- Preserve the CSS visual design (Arial sans-serif, light grey backdrop `#f4f6f8`, white centred 800 px container, primary button colour `#007bff`, hover colour `#0056b3`) verbatim
- Provide a `requirements.txt` that pins the Python dependencies so the application is reproducible

### 0.1.3 Implicit Requirements Surfaced from the User Prompt and Rule

The user's instruction "Refactor it to Python 3" combined with the rule "Refactor the code without changing the functionality" implies several requirements that are not stated explicitly:

- The five subject names and their on-screen order must remain Maths, Science, English, History, Computer (the original JavaScript `for...in` iteration order over the object literal; this iteration order is preserved when porting to a Python dict because Python 3.7+ guarantees insertion-ordered dict iteration)
- Blank or missing input fields must continue to be coerced to zero (the original `parseInt(... || 0)` semantics)
- The maximum possible total is 500 (five subjects × 100 marks each); the percentage formula `(total / 500) × 100` is fixed and must not be parameterised
- The grading scale uses inclusive lower bounds: A+ for percentage ≥ 90, A for ≥ 80, B for ≥ 70, C for ≥ 60, D for ≥ 50, and F otherwise — the cascade is in this order and the comparators stay `≥`
- The PDF filename uses the **on-screen rendered** student name (`document.getElementById('rName').innerText` in the original), not the raw form value — this means the PDF can only be generated after the on-screen report card has been produced; the Python rewrite must preserve that ordering
- No new persistent storage is introduced; the original application has no database, no authentication, and no user accounts, and these absences must be preserved (per the technology stack already established for the project)

## 0.2 Technical Interpretation

This refactoring translates to the following technical transformation strategy: the existing browser-only single-page application is restructured into an equivalent Python 3 web application using Flask 3.1.x for the HTTP layer, Jinja2 for HTML rendering (Jinja2 is bundled with Flask), and fpdf2 2.8.x for server-side PDF generation. The HTML markup, the CSS stylesheet, and a thin slice of client-side JavaScript glue (only enough to keep the original two-button workflow on a single page without a full-page reload) are preserved in form, while every piece of business logic that currently lives in the browser moves into Python.

### 0.2.1 Architecture Mapping

The transformation is one-to-one at the feature level. Every browser-side construct has a Python-side equivalent:

| Browser-side construct (source) | Python-side equivalent (target) | Notes |
|---------------------------------|--------------------------------|-------|
| Static HTML file loaded from `file://` or simple HTTP server | `templates/index.html` rendered by Flask via `render_template('index.html')` on the `/` route | Same DOM tree, IDs preserved |
| `style.css` linked from HTML | `static/css/style.css` served by Flask static handler; referenced via `url_for('static', filename='css/style.css')` | CSS content unchanged |
| `script.js` linked from HTML | `static/js/script.js` containing only AJAX glue; all business logic deleted from JS and recreated in Python | Optional thin client |
| `generateReport()` JavaScript function | Python helper `compute_report(form)` returning a dict, called from Flask route `POST /generate-report` which renders the report card region of `index.html` | Same five-subject sum, percentage, grade |
| `downloadPDF()` JavaScript function | Python helper `build_report_pdf(report)` returning a `BytesIO`, called from Flask route `POST /download-pdf` which responds with `send_file(...)` | Same lines, same filename `{name}_Report.pdf` |
| jsPDF v2.5.1 (browser) | fpdf2 2.8.x (Python) | Pure-Python pure-pip dependency; no system libs required |
| `document.getElementById('rName').innerText` (DOM writes) | Jinja2 `{{ report.name }}` interpolation in same span | Page structure unchanged |
| Client-side state in the DOM between `generateReport` and `downloadPDF` | Hidden form fields posted with the download form so the second request carries the computed values | Maintains the original "compute first, then download" sequence without a database |

### 0.2.2 Transformation Rules

The following transformation rules are applied uniformly across the port:

- Each JavaScript function in `script.js` is rewritten as a Python function in `app.py` that takes a dict (a Flask `request.form`) and returns a Python dict — input names and output keys match the original DOM ID names so the mapping is verifiable
- Numeric coercion `parseInt(value || 0)` becomes `int(value or 0)`; the truthiness rules align for the empty-string case that occurs when an HTML number input is left blank
- Template literals such as `` `${name}_Report.pdf` `` become f-strings `f"{name}_Report.pdf"`
- The HTML element IDs (`studentName`, `rollNumber`, `maths`, `science`, `english`, `history`, `computer`, `reportCard`, `rName`, `rRoll`, `marksTable`, `totalMarks`, `percentage`, `grade`) are preserved verbatim in the Jinja2 template; this guarantees that any external HTML/CSS test, screenshot diff, or accessibility audit done against the original page continues to work against the rewrite
- The CSS file `style.css` is copied verbatim into `static/css/style.css`; no selectors, colours, or layout values change
- The `<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js">` CDN tag is **removed** because PDF generation is now server-side; this also closes the known security gap noted earlier in the technical specification (the original CDN tag had no Subresource Integrity hash)
- The original two-button flow (`onclick="generateReport()"` and `onclick="downloadPDF()"`) is preserved by submitting the form to two separate Flask endpoints using a small fetch-based client helper that updates the report card region in place, so the user still sees the on-screen card before downloading the PDF

## 0.3 Scope Boundaries

The refactor is scoped narrowly to producing a Python 3 implementation of the existing six implemented features (F-001 through F-006) in the same repository. Every aspirational feature flagged in the existing technical specification (F-007 through F-012) is explicitly out of scope.

### 0.3.1 Exhaustively In Scope

The following paths are in scope. All target paths are relative to the repository root `/tmp/blitzy/Student_Mngt/15-May-26-Br2_c59dc0/`.

- Source transformations:
    - `Student Report Generator Javascript Pdf.pdf` — REFERENCE source-of-truth for the original JavaScript/HTML/CSS code (not modified)
    - `Readme.md` — UPDATE to reflect the Python 3 stack and the new run instructions

- Python application creation:
    - `app.py` — CREATE — the Flask application module containing the route definitions and the two helper functions (`compute_report`, `build_report_pdf`) that replace the original JavaScript functions
    - `templates/index.html` — CREATE — the Jinja2 template that replaces the original `index.html` embedded in the PDF (preserves the same form, the same report card region, and the same DOM IDs)
    - `static/css/style.css` — CREATE — verbatim copy of the original `style.css` from the PDF
    - `static/js/script.js` — CREATE — a thin client-side helper (only enough to submit the form via fetch and update the report card region without a full page reload, preserving the original two-button single-page UX); all business logic has been moved server-side

- Dependency and configuration files (rule-mandated for a reproducible Python 3 environment):
    - `requirements.txt` — CREATE — pinned Python dependencies (Flask, fpdf2)
    - `.gitignore` — CREATE — standard Python project hygiene (e.g. `__pycache__/`, `.venv/`, `*.pyc`)

- Wildcard summary of target-side scope:
    - `*.py` — all CREATE — currently this is the single file `app.py`; the wildcard is provided for forward compatibility if helper modules are split out
    - `templates/*.html` — all CREATE — currently this is the single file `index.html`
    - `static/css/*.css` — all CREATE — currently this is the single file `style.css`
    - `static/js/*.js` — all CREATE — currently this is the single file `script.js`

### 0.3.2 Explicitly Out of Scope

- Aspirational features documented in the technical specification but not implemented in the source code: persistent storage (F-007), multi-student management (F-008), charts and analytics (F-009), teacher comments (F-010), digital signatures (F-011), Excel export (F-012). The user did not request any of these and the rule constrains the refactor to behaviour preservation
- Database introduction (no SQLite, PostgreSQL, MongoDB, or other persistence layer)
- Authentication, authorization, sessions, CSRF tokens beyond Flask defaults, or user accounts
- Backend frameworks other than Flask (no Django, FastAPI, Pyramid, Bottle)
- PDF libraries other than fpdf2 (no ReportLab, WeasyPrint, PDFKit, xhtml2pdf, Playwright)
- Containerization (no Dockerfile, docker-compose.yml)
- CI/CD pipelines (no `.github/workflows/`, no `.gitlab-ci.yml`, no Jenkinsfile)
- Cloud infrastructure-as-code (no Terraform, no CloudFormation, no AWS/GCP/Azure provisioning)
- The `.git/` directory and its contents
- The PDF file `Student Report Generator Javascript Pdf.pdf` itself — it remains in place as the immutable source-of-truth reference

### 0.3.3 Design System Alignment

Not applicable. The user did not specify a design system (Ant Design, Material UI, SAP UI5, Shadcn/ui, or any proprietary library) in the prompt. The source UI in the PDF uses plain custom CSS with no component library, no design tokens, and no theme system. Per the Design System Alignment Protocol, when no library is specified the CSS is preserved 1:1 as a static asset; the protocol's component-mapping, token-mapping, and gap-inventory tables are therefore omitted from this AAP.

## 0.4 Target Design

The refactored repository layout is a canonical Flask project structure: a single application module `app.py` at the root, sibling `templates/` and `static/` directories that Flask autodiscovers via `flask.Flask(__name__)`, a dependency manifest at the root, and the original Readme.md updated to describe the Python 3 stack. The pre-existing PDF and the existing Readme.md stay in place; everything else is newly created.

### 0.4.1 Refactored Repository Structure

```text
/tmp/blitzy/Student_Mngt/15-May-26-Br2_c59dc0/
├── Student Report Generator Javascript Pdf.pdf  (REFERENCE — unchanged source-of-truth)
├── Readme.md                                    (UPDATE — Python 3 run instructions)
├── app.py                                       (CREATE — Flask app + helper functions)
├── requirements.txt                             (CREATE — Flask, fpdf2)
├── .gitignore                                   (CREATE — Python hygiene)
├── templates/
│   └── index.html                               (CREATE — Jinja2 template; mirrors original HTML)
└── static/
    ├── css/
    │   └── style.css                            (CREATE — verbatim copy of original CSS)
    └── js/
        └── script.js                            (CREATE — thin fetch glue, no business logic)
```

### 0.4.2 Module Responsibilities

| Module | Responsibility | Replaces |
|--------|----------------|----------|
| `app.py` | Defines the Flask app, three routes (`GET /`, `POST /generate-report`, `POST /download-pdf`), the helper `compute_report(form) -> dict` that computes total/percentage/grade, and the helper `build_report_pdf(report) -> BytesIO` that emits the PDF | Original `script.js` business logic |
| `templates/index.html` | Renders the form and the report card region using Jinja2; preserves all original DOM IDs; loads the static CSS and JS | Original `index.html` embedded in the PDF |
| `static/css/style.css` | Layout, typography, button styles, and table borders | Original `style.css` embedded in the PDF (verbatim) |
| `static/js/script.js` | Submits the form to `/generate-report` via `fetch`, injects the returned HTML fragment into `#reportCard`, and submits the hidden form to `/download-pdf` when the download button is pressed | Original `script.js` button glue only (business logic removed) |
| `requirements.txt` | Pins exact runtime dependencies for reproducibility | New file — no equivalent in the JavaScript source |
| `.gitignore` | Excludes virtual environments, byte-compiled Python, and IDE folders from version control | New file — no equivalent in the JavaScript source |
| `Readme.md` | Updated user-facing documentation for the Python stack | Existing Readme.md (which mirrored the JS code) |

### 0.4.3 Design Pattern Applications

- **Server-Rendered MVC (Flask + Jinja2)** — the Jinja2 template is the View, the Flask route handlers are the Controllers, and the Python dict returned by `compute_report` is the Model. This is the smallest pattern that preserves the original HTML form workflow when the runtime moves from the browser to a Python server
- **Functional decomposition mirroring the source** — the two original JavaScript functions become two Python helpers with deliberately matching names and shapes (`compute_report` ↔ `generateReport`; `build_report_pdf` ↔ `downloadPDF`). This keeps the refactor auditable: a reviewer can compare each line of the original JS to each line of the Python helper
- **Stateless request handling** — instead of holding state in the browser DOM between two button presses (the original pattern), the Python rewrite carries the computed values in hidden form fields on the download form, so the second HTTP request is fully self-contained. This is the minimum state-management change required to move from a browser-DOM runtime to a stateless server runtime, and it stays consistent with the project's "no database" boundary
- **Externalised dependency pinning** — `requirements.txt` records exact versions so the install is reproducible, replacing the original implicit dependency on a CDN URL

### 0.4.4 UI Design

The user interface remains visually and structurally identical to the original. The Jinja2 template reproduces the original HTML element tree element-for-element, with three changes:

- The `<link rel="stylesheet" href="style.css">` becomes `<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">`
- The `<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>` CDN tag is removed
- The `<script src="script.js"></script>` becomes `<script src="{{ url_for('static', filename='js/script.js') }}"></script>`

The `<form class="form-section">` element gains a `method="post"` attribute and the two `<button onclick=...>` attributes are kept for backwards-compatible behaviour but their target JavaScript functions now make `fetch` requests against the Flask endpoints instead of computing locally. The report card region (`<div class="report-card" id="reportCard">`) keeps its inner span IDs (`rName`, `rRoll`, `totalMarks`, `percentage`, `grade`) and its `<table>` with the `<tbody id="marksTable">` so the on-screen output is byte-equivalent to the original after rendering.

## 0.5 Transformation Mapping

Every target file is mapped to a source file. The PDF is the authoritative source for the embedded JavaScript/HTML/CSS; `Readme.md` is a mirror of the same code that gets updated to describe the Python 3 stack. All Python and template artefacts are CREATE operations because no Python file exists in the repository today.

### 0.5.1 File-by-File Transformation Plan

| Target File | Transformation | Source File | Key Changes |
|-------------|----------------|-------------|-------------|
| `app.py` | CREATE | `Student Report Generator Javascript Pdf.pdf` (the embedded `script.js` block on pages 4–6) | Translate `generateReport()` to Python helper `compute_report(form_data)`; translate `downloadPDF()` to Python helper `build_report_pdf(report)`; define Flask app, the `GET /` route that renders the empty form, the `POST /generate-report` route that returns the rendered report card region, and the `POST /download-pdf` route that returns the PDF via `send_file`; replace jsPDF API calls with fpdf2 API calls |
| `templates/index.html` | CREATE | `Student Report Generator Javascript Pdf.pdf` (the embedded `index.html` block on pages 1–3) | Wrap the original HTML in a Jinja2 template; replace literal `style.css` / `script.js` paths with `url_for('static', ...)`; remove the jsPDF CDN script tag; replace inline `document.getElementById(...).innerText = X` outputs with Jinja2 `{{ X }}` expressions; preserve every element ID and every CSS class verbatim |
| `static/css/style.css` | CREATE | `Student Report Generator Javascript Pdf.pdf` (the embedded `style.css` block on pages 3–4) | Verbatim copy; no rules added, removed, or modified |
| `static/js/script.js` | CREATE | `Student Report Generator Javascript Pdf.pdf` (the embedded `script.js` block on pages 4–6) | **REFERENCE only** for the original button bindings; the new file is a small fetch-based client that POSTs to `/generate-report` and `/download-pdf`. All business logic (subject sum, percentage formula, grade cascade, PDF drawing) is deleted from JS and recreated in Python |
| `requirements.txt` | CREATE | — (no equivalent source file; rule-mandated) | Pins `Flask==3.1.3` and `fpdf2==2.8.7`; transitive dependencies install automatically |
| `.gitignore` | CREATE | — (no equivalent source file; rule-mandated) | Excludes `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.idea/`, `.vscode/`, `*.egg-info/` |
| `Readme.md` | UPDATE | `Readme.md` (existing) | Replace JavaScript run instructions with Python run instructions (`pip install -r requirements.txt`, `flask run`); update the project structure description to match the new layout; update the technology stack description to list Python 3.12 / Flask 3.1.x / fpdf2 2.8.x / Jinja2; keep the feature list (F-001 through F-006) intact because functionality is preserved |
| `Student Report Generator Javascript Pdf.pdf` | REFERENCE | (self) | Not modified — kept as the immutable source-of-truth for the original JavaScript implementation |

### 0.5.2 Cross-File Dependencies

The Python module graph is intentionally flat to keep the refactor close to the single-file JavaScript original:

```text
app.py
  ├─ imports: flask.Flask, flask.render_template, flask.request, flask.send_file, fpdf.FPDF, io.BytesIO
  ├─ defines: compute_report(form), build_report_pdf(report), three route handlers
  └─ renders:  templates/index.html (via Flask autodiscovery of the templates/ folder)

templates/index.html
  ├─ extends/loads: nothing (single template)
  └─ references:  static/css/style.css and static/js/script.js (via url_for)

static/css/style.css
  └─ no dependencies

static/js/script.js
  └─ no dependencies; uses the browser-native fetch API
```

### 0.5.3 Import Statement Changes

For each file the import changes are:

- `app.py` — new file; imports are:
    - `from flask import Flask, render_template, request, send_file`
    - `from fpdf import FPDF`
    - `from io import BytesIO`
- `templates/index.html` — no Python imports; HTML asset references change from `<link rel="stylesheet" href="style.css">` to `<link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">`, and from `<script src="script.js"></script>` to `<script src="{{ url_for('static', filename='js/script.js') }}"></script>`; the `<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js">` line is deleted
- `static/css/style.css` — no imports in either source or target
- `static/js/script.js` — no imports in either source or target; the new file uses only the browser-native `fetch` and `FormData` globals
- `Readme.md` — no imports; the prose changes from describing a JavaScript stack to describing a Python stack

### 0.5.4 Wildcard Patterns

Wildcards are limited to forward-compatibility convenience patterns. The current scope contains exactly one file per pattern:

- `*.py | CREATE` — the single file `app.py`
- `templates/*.html | CREATE` — the single file `index.html`
- `static/css/*.css | CREATE` — the single file `style.css`
- `static/js/*.js | CREATE` — the single file `script.js`

No leading wildcards are used.

### 0.5.5 One-Phase Execution

The entire refactor is executed in **one phase**. All seven create/update operations land in the same change set; the application is functional immediately after that single phase because every file required to serve the Flask app and generate a PDF exists at the end of the phase.

## 0.6 Dependency Inventory

The Python rewrite introduces exactly two direct third-party dependencies — Flask for the web framework and fpdf2 for PDF generation — and a Python runtime requirement of 3.10 or newer (3.12 chosen as the pin target because it is installed in the working environment and is supported by both libraries). Every other package is a transitive dependency that pip resolves automatically.

### 0.6.1 Key Public Packages

| Registry | Name | Version | Purpose |
|----------|------|---------|---------|
| PyPI | `Flask` | `3.1.3` | WSGI web framework; routes, request handling, Jinja2 templating |
| PyPI | `fpdf2` | `2.8.7` | Pure-Python PDF generation library; server-side replacement for jsPDF |
| python.org | `python` | `3.12.x` | Runtime — required by Flask 3.1 (≥ 3.9) and fpdf2 2.8 (≥ 3.10); 3.12 is verified present in the working environment |

Transitive dependencies pulled in automatically by the two direct dependencies:

- Pulled in by Flask 3.1: Werkzeug (≥ 3.1), Jinja2, MarkupSafe, ItsDangerous (≥ 2.2), Click (≥ 8.1.3), Blinker (≥ 1.9)
- Pulled in by fpdf2 2.8: Pillow, defusedxml, fontTools

No private packages are required.

### 0.6.2 Dependency Changes

This is a cross-language port, so the "before" and "after" dependency manifests are entirely different. The mapping is:

| Source dependency (JavaScript) | Status in target | Target dependency (Python) |
|--------------------------------|------------------|----------------------------|
| jsPDF v2.5.1 (loaded from `cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js`) | Removed | Replaced by `fpdf2==2.8.7` |
| Browser DOM API (built-in, no package) | Removed (only thin glue remains) | Replaced by `Flask==3.1.3` + Jinja2 (bundled with Flask) for server-side rendering |
| HTML5 / CSS3 (no package) | Preserved | No change — markup and styles are static assets served by Flask |

The single new file `requirements.txt` contains:

```text
Flask==3.1.3
fpdf2==2.8.7
```

### 0.6.3 Import Refactoring

There are no Python imports to refactor because there is no pre-existing Python code in the repository. All Python imports in `app.py` are net-new and listed in Section 0.5.3.

### 0.6.4 External Reference Updates

- `templates/index.html` — the two relative asset paths and the one CDN URL are updated as described in Section 0.5.3
- `Readme.md` — text references to JavaScript files are replaced with references to the corresponding Python files; the technology stack section gets new entries for Python, Flask, and fpdf2; the run instructions section replaces "open `index.html` in a browser" with "create a virtual environment, `pip install -r requirements.txt`, then `flask run`"

## 0.7 Special Analysis

The cross-language port from browser JavaScript to Python 3 has a handful of language-level translation rules that, if missed, would silently change behaviour. The analysis below names each rule, gives the source idiom, the target idiom, and the reason the two are observationally equivalent.

### 0.7.1 Language-Level Translation Rules

- **Blank-input coercion to zero.** The source uses `parseInt(document.getElementById('maths').value || 0)`. The HTML `<input type="number">` returns the empty string `""` for an empty field; `"" || 0` yields `0` in JavaScript and `parseInt(0) === 0`. The Python equivalent is `int(form.get('maths') or 0)` — when Flask's `request.form.get('maths')` returns `""` for an empty field, `"" or 0` evaluates to `0` (because the empty string is falsy in Python), and `int(0) == 0`. The two idioms are observationally equivalent for every blank or numeric-string input
- **Subject order.** The source iterates `for (let subject in subjects)` over an object literal. ECMAScript guarantees string-keyed property iteration in insertion order. Python's `dict` (3.7+) also guarantees insertion-ordered iteration. Therefore declaring the Python dict with the same key order (`Maths`, `Science`, `English`, `History`, `Computer`) preserves both the on-screen table row order and the order of cells produced by fpdf2
- **Percentage formula and formatting.** The source computes `const percentage = (total / 500) * 100;` and renders `percentage.toFixed(2)`. The Python equivalent computes `percentage = (total / 500) * 100` (Python 3 `/` is true division returning a float) and renders `f"{percentage:.2f}"`. The arithmetic is IEEE-754 double precision in both runtimes, and the formatting is two-decimal rounding in both; the printable strings match for all inputs in the closed integer range `[0, 500]`
- **Grade cascade.** The source uses a top-to-bottom `if / else if` chain with comparators `>=`. The Python rewrite uses `if / elif / else` with `>=` in the same order. The thresholds 90, 80, 70, 60, 50 and the initial default `'F'` are preserved
- **PDF filename derivation.** The source reads the on-screen rendered name (`document.getElementById('rName').innerText`) and builds the filename `` `${name}_Report.pdf` ``. The Python rewrite carries the same already-rendered name through the hidden field on the download form and uses it to build the filename `f"{name}_Report.pdf"`, then sets it on `send_file(..., download_name=...)` so the browser sees the same `Content-Disposition: attachment; filename="<name>_Report.pdf"` header
- **PDF layout coordinates and font sizes.** The source uses jsPDF's millimetre coordinate system (default for `new jsPDF()`) and font sizes 18 and 12. fpdf2 also defaults to millimetres (`FPDF(unit="mm", format="A4")`) and accepts `set_font("Helvetica", size=18)` and `set_font("Helvetica", size=12)`. The five labelled lines are placed at the same vertical offsets (20, 40, 50, 60, 70, 80) via `pdf.text(20, 20, ...)` style calls so the rendered PDF is positionally equivalent to the original. (Note: jsPDF positions text at the baseline and so does fpdf2 when using the `text()` method, so the y-coordinates need no adjustment)
- **`innerText` replacement with Jinja2 interpolation.** The source assigns values into spans via `document.getElementById(...).innerText = X`. The Python rewrite renders the same values via Jinja2 `{{ X }}` inside the same spans. Jinja2 autoescapes HTML by default, which is a security strengthening that does not change behaviour for any input that does not contain HTML special characters; for the student's name field this is a net improvement
- **CDN removal closes a known SRI gap.** Removing the unhashed jsPDF CDN script eliminates the previously documented security gap (an external CDN script tag with no Subresource Integrity attribute); functionality is unchanged because the PDF is now generated server-side

### 0.7.2 Behaviour-Preservation Strategy

To make the equivalence verifiable, the refactor adopts three discipline rules:

- **Verifiable equivalence at the helper boundary.** `compute_report(form_data)` returns a dict with the keys `name`, `roll`, `subjects`, `total`, `percentage`, `grade`. Any test that calls this helper with the same form values used to test the original JavaScript implementation must return the same field values; this makes the port machine-checkable
- **Verifiable equivalence at the PDF text boundary.** `build_report_pdf(report)` returns a `BytesIO` containing a PDF whose extracted text contains the five lines `Student Name: <name>`, `Roll Number: <roll>`, `Total Marks: <total>`, `Percentage: <percentage>%`, `Grade: <grade>` in the same order as the original; the title line `Student Report Card` appears at the top
- **Verifiable equivalence at the HTML boundary.** The Jinja2 template, after rendering with empty initial state, must produce HTML whose tag tree and IDs match the original `index.html` byte-for-byte except for the three asset-URL changes and the removed CDN tag

### 0.7.3 Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Subject iteration order diverges between JS object and Python dict | Very low — both runtimes specify insertion-ordered iteration | Declare the Python dict literal with the same key order as the source |
| Floating-point percentage differs after `toFixed(2)` vs `f"{:.2f}"` rounding modes | Low — both libraries round-half-away-from-zero for two decimals on these magnitudes | Test boundary inputs (e.g. all 449/500 → 89.80, all 450/500 → 90.00) |
| PDF text content shifts due to font-metric differences between jsPDF Helvetica and fpdf2 Helvetica | Low — both libraries use the PDF built-in Helvetica which is a standard font | Use `set_font("Helvetica", size=18 / 12)` and place text via absolute coordinates as in the source |
| Browser session loses computed state between the two button clicks | Mitigated by design | Hidden form fields carry the computed values to the second endpoint, replicating the original DOM-as-buffer pattern |

## 0.8 Refactoring Rules

The refactor is governed by one explicit user-supplied rule plus a small set of derived constraints that operationalise that rule for a cross-language port.

### 0.8.1 User-Specified Rules

| Rule name | Rule content (verbatim) |
|-----------|-------------------------|
| `Ajit_Test_Refactor` | Refactor the code without changing the functionality. |

### 0.8.2 Operational Constraints Derived from the Rule

To make the rule "Refactor the code without changing the functionality" verifiable for this specific port, the following invariants must hold across the source-to-target translation:

- **Identical inputs.** The HTML form continues to accept exactly seven values with exactly these element IDs: `studentName`, `rollNumber`, `maths`, `science`, `english`, `history`, `computer`. No fields are added, removed, or renamed
- **Identical arithmetic.** Total = sum of the five subject marks; percentage = `(total / 500) * 100`; percentage is rendered with two decimals
- **Identical grading rubric.** A+ for percentage ≥ 90, A for ≥ 80, B for ≥ 70, C for ≥ 60, D for ≥ 50, F otherwise. The cascade order and the comparators are preserved
- **Identical on-screen anchors.** The report card region must continue to expose `rName`, `rRoll`, `marksTable`, `totalMarks`, `percentage`, and `grade` so any external integration that queries the DOM continues to work
- **Identical PDF.** The downloaded PDF must contain the title `Student Report Card` and the five labelled lines in the same order; the filename must follow the pattern `{name}_Report.pdf` derived from the rendered (not the raw form) name
- **No new persistent state.** No database, no on-disk cache; the application remains stateless across requests beyond the in-flight form payload
- **No new external services.** The CDN dependency on `cdnjs.cloudflare.com` is removed; no other external service is introduced

### 0.8.3 Special Instructions and Constraints

- **Migration target is the same repository.** No new repository is created. All new Python and template files are placed at `/tmp/blitzy/Student_Mngt/15-May-26-Br2_c59dc0/` next to the existing PDF and Readme.md
- **The PDF stays untouched.** The file `Student Report Generator Javascript Pdf.pdf` is the immutable source-of-truth for the original JavaScript implementation and remains in the repository unmodified
- **User Example: PDF read instruction.** The user explicitly required the platform to read the PDF, confirm successful reading, and state the source language before refactoring. The platform has done so:
    - The PDF was read end-to-end (all 7 pages, 87,443 bytes)
    - The platform confirms the code in the PDF was successfully read and analyzed
    - The programming language used in the PDF is **JavaScript** (with HTML5 markup and CSS3 styling)
- **User Example: refactor target.** The user wrote "refactor it to Python 3". This AAP interprets that as a runtime-level migration (rather than producing a Python script with no UI) because the rule "without changing the functionality" requires that the form-based UX, the on-screen report card, and the PDF download all continue to work. A Flask + Jinja2 + fpdf2 stack is the minimum-surface Python combination that preserves all six implemented features
- **No additional rules were provided.** The user did not specify a maximum line length, a docstring style, an HTTP port, a host binding, or any other coding-style or runtime-configuration constraint. Reasonable Flask defaults (e.g. development server on `127.0.0.1:5000` for local use) apply

## 0.9 References

All claims made in this Agent Action Plan are grounded in the repository content (the PDF and the Readme.md), the existing Technical Specification sections, and a small set of public package registries. Citations use the form `[<path>:<locator>]`.

### 0.9.1 Repository Files Inspected

| Path | Locator | Purpose |
|------|---------|---------|
| `Student Report Generator Javascript Pdf.pdf` | pages 1–7 | Authoritative source for the original JavaScript (`script.js`), HTML (`index.html`), and CSS (`style.css`) implementation [Student Report Generator Javascript Pdf.pdf:pp.1-7] |
| `Readme.md` | lines 1–238 | Mirror copy of the JavaScript / HTML / CSS source code plus prose documentation of features, structure, and usage [Readme.md:L1-L238] |
| `.blitzyignore` | — | Searched repository-wide; no `.blitzyignore` files exist [inferred — no direct source from `bash`/`find` search returning empty result] |

### 0.9.2 Technical Specification Sections Consulted

| Section | Locator | What was relied upon |
|---------|---------|----------------------|
| 1.2 SYSTEM OVERVIEW | §1.2 | Confirms the project scope, user-facing capabilities, and success criteria for the original application [Tech Spec:§1.2] |
| 2.1 FEATURE CATALOG | §2.1 | Confirms the six implemented features F-001 through F-006 (Student Detail Entry, Automated Marks Computation, Automated Grade Assignment, On-Screen Report Card Rendering, PDF Report Export, Responsive UI) and the six aspirational features F-007 through F-012 that are out of scope for this refactor [Tech Spec:§2.1] |
| 3.1 PROGRAMMING LANGUAGES | §3.1 | Confirms HTML5 / CSS3 / JavaScript ES5+ as the only languages used in the source [Tech Spec:§3.1] |
| 3.7 TECHNOLOGY STACK SUMMARY | §3.7 | Confirms the non-applicability of backend frameworks, databases, build tooling, CI/CD, cloud, and authentication for the source application [Tech Spec:§3.7] |
| 5.1 HIGH-LEVEL ARCHITECTURE | §5.1 | Confirms the static-single-page client-side architecture, the DOM-as-transient-state pattern between `generateReport()` and `downloadPDF()`, and the CDN dependency on jsPDF v2.5.1 without Subresource Integrity [Tech Spec:§5.1] |

### 0.9.3 External References

| Source | URL / Locator | Reason consulted |
|--------|---------------|------------------|
| Flask PyPI page | `https://pypi.org/project/Flask/` | Verify the latest stable Flask version is `3.1.3` and its Python compatibility floor is `>=3.9` |
| fpdf2 PyPI page | `https://pypi.org/project/fpdf2/` | Verify the latest stable fpdf2 version is `2.8.7` (released 2026-02-28) and its Python compatibility floor is `>=3.10` |
| Flask Installation docs | `https://flask.palletsprojects.com/en/stable/installation/` | Confirm Flask's transitive dependencies (Werkzeug, Jinja2, MarkupSafe, ItsDangerous, Click, Blinker) install automatically |

### 0.9.4 Attachments and Metadata

| Attachment | Size | Pages | Concise summary |
|------------|------|-------|-----------------|
| `Student Report Generator Javascript Pdf.pdf` | 87,443 bytes | 7 pages | Contains the complete `index.html`, `style.css`, and `script.js` source for a single-page browser Student Report Generator. Embeds five subject inputs, a percentage calculator, a six-tier grade cascade, and a jsPDF v2.5.1-driven downloadable PDF report. This is the file the user asked the platform to read |
| `Readme.md` | 6,146 bytes | n/a | Markdown documentation that mirrors the same `index.html`, `style.css`, and `script.js` source code inside fenced code blocks, plus prose covering project description, technology stack, features, file structure, usage instructions, and notes |

### 0.9.5 Figma Screens

None provided. The user did not attach any Figma URLs.

### 0.9.6 Search Log

| # | Tool | Target | Purpose |
|---|------|--------|---------|
| 1 | `bash` | `find / -name ".blitzyignore" 2>/dev/null` | Verify there are no ignore-pattern files anywhere on the working volume |
| 2 | `get_source_folder_contents` | folder_path `""` | Discover repository root contents (returned only `Readme.md` and the PDF) |
| 3 | `bash` | `ls -la /tmp/blitzy/Student_Mngt/15-May-26-Br2_c59dc0/` | Confirm absolute paths of repository files and their sizes |
| 4 | `bash` | `find / -name "*.pdf" 2>/dev/null` | Locate the PDF the user referred to |
| 5 | `bash` | `git -C /tmp/blitzy/Student_Mngt/15-May-26-Br2_c59dc0 log --oneline` | Establish the repository history baseline (single upload commit) |
| 6 | `read_file` | `Readme.md` (lines 1, -1) | Retrieve the full mirrored source and project description |
| 7 | `read_file` | `Student Report Generator Javascript Pdf.pdf` (pages 1, -1) | Retrieve the embedded source code from the authoritative PDF |
| 8 | `get_tech_spec_section` | `1.2 SYSTEM OVERVIEW` | Background on project scope and capabilities |
| 9 | `get_tech_spec_section` | `2.1 FEATURE CATALOG` | Confirm implemented vs aspirational features |
| 10 | `get_tech_spec_section` | `3.1 PROGRAMMING LANGUAGES` | Confirm the source language inventory |
| 11 | `get_tech_spec_section` | `3.7 TECHNOLOGY STACK SUMMARY` | Confirm absent technology categories (backend, DB, build, CI/CD, cloud) |
| 12 | `get_tech_spec_section` | `5.1 HIGH-LEVEL ARCHITECTURE` | Confirm architecture, data flow, and the jsPDF CDN integration point |
| 13 | `web_search` | "Flask Python 3.12 latest stable version 2026" | Verify pinned Flask version `3.1.3` and Python compatibility |
| 14 | `web_search` | "fpdf2 vs ReportLab Python PDF generation library 2026" | Confirm fpdf2 is a pure-Python, dependency-light, server-side-friendly replacement for jsPDF |
| 15 | `web_search` | "fpdf2 latest version pypi 2026" | Verify pinned fpdf2 version `2.8.7` |

