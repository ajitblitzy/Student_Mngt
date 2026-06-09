# Changelog

All notable changes to the **Student Report Generator** project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Non-academic / co-curricular activities in the student report.** The report now records and displays **Sports**, **Elocution**, and **Drama** participation alongside the existing academic results, and these activities are included in the exported PDF. `Source: Readme.md:L9-L17`, `Source: Readme.md:L333-L336`
- **Three new free-text input fields** for capturing participation/achievement descriptors (for example, `Winner - District` or `Participated`): `#sports`, `#elocution`, and `#drama`. They mirror the existing per-subject input pattern on the form. `Source: Readme.md:L86-L89`, `Source: Readme.md:L134-L140`
- **New report-card section "Co-Curricular / Non-Academic Activities",** rendered as a table whose body is `#activitiesTable`, mirroring the existing academic marks table. `Source: Readme.md:L115-L124`, `Source: Readme.md:L142`
- **`generateReport()` now collects the non-academic / co-curricular activities into an `activities` map** (`{ Sports, Elocution, Drama }`) and renders each entry as a row in `#activitiesTable`, in addition to building the academic marks table. `Source: Readme.md:L275-L302`, `Source: Readme.md:L342`
- **`downloadPDF()` now appends the activity lines below the grade line** in the exported PDF, so the downloaded `<name>_Report.pdf` includes the non-academic / co-curricular activities. Client-side PDF generation continues to use jsPDF **2.5.1** (no dependency change). `Source: Readme.md:L326-L336`, `Source: Readme.md:L338`, `Source: Readme.md:L69`
- **New focused feature guide `docs/non-academic-activities.md`,** documenting the data model, UI fields, report-card rendering, PDF output, a worked example, behavior notes, and troubleshooting for this capability. `Source: Readme.md:L11`, `Source: Readme.md:L348`
- **Activities are non-scoring.** Recording Sports, Elocution, and Drama does **not** change `total`, `percentage`, or grade: the percentage formula `percentage = (total / 500) * 100` and the grade ladder (A+ ≥ 90, A ≥ 80, B ≥ 70, C ≥ 60, D ≥ 50, else F) remain **unchanged**. The non-academic / co-curricular activities are reported separately as participation/achievement descriptors. `Source: Readme.md:L253-L267`, `Source: Readme.md:L344`
