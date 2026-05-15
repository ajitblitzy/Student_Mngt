# Student Report Generator (Python 3)

## Overview
This project allows users to:
- Enter student details using a form
- Calculate total marks and percentage
- Generate a formatted student report
- Export the report as a PDF file

The application is implemented as a Python 3 Flask web application that renders the report card server-side and produces the downloadable PDF on the server.

---

# Project Structure

```text
Student_Mngt/
│
├── Student Report Generator Javascript Pdf.pdf   # Reference source-of-truth (original JS implementation)
├── Readme.md                                     # This documentation
├── app.py                                        # Flask application module
├── requirements.txt                              # Python dependencies
├── .gitignore                                    # Python project hygiene
├── templates/
│   └── index.html                                # Jinja2 template
└── static/
    ├── css/
    │   └── style.css                             # Styles
    └── js/
        └── script.js                             # Thin client-side fetch glue
```

---

# Features

- Enter student details
- Calculate percentage automatically
- Generate grade
- Download report as PDF
- Responsive UI

---

# Technologies Used

- Python 3.12
- Flask 3.1.x (WSGI web framework)
- Jinja2 (bundled with Flask, used for HTML templating)
- fpdf2 2.8.x (server-side PDF generation, replaces jsPDF)
- HTML5
- CSS3

---

# How to Run

1. Clone or download the project.
2. (Recommended) Create and activate a virtual environment:
   - `python -m venv .venv`
   - On Linux/Mac: `source .venv/bin/activate`
   - On Windows: `.venv\Scripts\activate`
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Run the Flask development server:
   - `flask run` (or `python app.py`)
5. Open `http://127.0.0.1:5000` in a browser.
6. Enter student details, click **Generate Report** to see the on-screen report, then click **Download PDF** to download a PDF file.

---

# Future Enhancements

- Add database support
- Add multiple student report management
- Add charts and analytics
- Add teacher comments
- Add digital signature support
- Export reports to Excel
