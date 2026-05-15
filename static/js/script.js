/*
 * Student Report Generator - Client-side glue script.
 *
 * Thin client-side helper for the Flask-based Student Report Generator
 * application. All business logic that originally lived in this file
 * (computing total/percentage/grade in generateReport(); generating a
 * downloadable PDF via jsPDF in downloadPDF()) has been moved to the
 * Python server (app.py + fpdf2). This file contains ONLY:
 *
 *   1. A submit-event listener on #reportForm that intercepts the
 *      Generate Report form submission, POSTs the form values to
 *      /generate-report via fetch, and copies the rendered
 *      #reportCard region (plus the hidden #downloadForm inputs)
 *      from the response into the current page so the user sees the
 *      populated report card without a full-page reload.
 *
 *   2. No-op globals window.generateReport() and window.downloadPDF()
 *      defined to satisfy the inline onclick="..." attributes in
 *      templates/index.html. The Download PDF button is
 *      type="submit" form="downloadForm", so the browser submits the
 *      hidden download form naturally to /download-pdf and handles
 *      the Content-Disposition: attachment response as a file
 *      download.
 *
 * Uses only browser-native APIs: fetch, FormData, DOMParser,
 * addEventListener, getElementById, querySelector. No external
 * libraries (no jQuery, no jsPDF, no framework). The application
 * also degrades gracefully without JavaScript: both forms have
 * native action/method attributes so they submit normally if this
 * script fails to load or is disabled.
 *
 * Behaviour preservation (per AAP rule "Ajit_Test_Refactor"):
 *   - Click "Generate Report" -> on-screen report card appears
 *     populated with name, roll, marks table, total, percentage,
 *     and grade.
 *   - Click "Download PDF" -> browser downloads a PDF file named
 *     "{name}_Report.pdf" via Content-Disposition: attachment.
 *
 * The original script.js (browser-side ECMAScript using ES5 + a
 * small set of ES6 features, loaded jsPDF v2.5.1 from cdnjs) is
 * preserved verbatim inside Student Report Generator Javascript
 * Pdf.pdf at the repository root for historical reference.
 */

(function () {
    'use strict';

    /*
     * Re-entry guard. Set to true while a /generate-report fetch is
     * in flight, false otherwise. Prevents overlapping submissions if
     * the user clicks "Generate Report" rapidly several times in a row
     * or if both the inline onclick handler and the submit-event
     * listener attempt to start a fetch on the same click.
     */
    let _submissionInFlight = false;

    /*
     * Hidden input "name" attributes inside #downloadForm in
     * templates/index.html. After /generate-report returns the
     * fully rendered page, these inputs in the response carry the
     * server-computed name, roll, total, formatted percentage, and
     * grade. We copy those values onto the current page's
     * #downloadForm so the subsequent "Download PDF" click submits
     * the right payload to /download-pdf.
     */
    const DOWNLOAD_FIELD_NAMES = ['name', 'roll', 'total', 'percentage_str', 'grade'];

    /*
     * POSTs #reportForm to /generate-report via fetch, then patches
     * the populated #reportCard region and #downloadForm hidden
     * input values into the current document. Silently logs and
     * swallows any error so the page remains usable on failure
     * (mirroring the original script.js which surfaced nothing to
     * the user).
     */
    async function submitReportForm() {
        if (_submissionInFlight) {
            return;
        }

        const form = document.getElementById('reportForm');
        if (!form) {
            return;
        }

        _submissionInFlight = true;

        try {
            const formData = new FormData(form);
            const response = await fetch('/generate-report', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Server returned status ${response.status}`);
            }

            const html = await response.text();
            updateReportCardFromHtml(html);
        } catch (error) {
            console.error('Error generating report:', error);
        } finally {
            _submissionInFlight = false;
        }
    }

    /*
     * Parses the server response (a full HTML page rendered from
     * templates/index.html with the computed report) and copies the
     * populated #reportCard innerHTML and #downloadForm hidden input
     * values into the current document. Uses DOMParser so embedded
     * <script> tags in the response (if any) are NOT executed.
     */
    function updateReportCardFromHtml(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const newReportCard = doc.getElementById('reportCard');
        const currentReportCard = document.getElementById('reportCard');
        if (newReportCard && currentReportCard) {
            currentReportCard.innerHTML = newReportCard.innerHTML;
        }

        const newDownloadForm = doc.getElementById('downloadForm');
        const currentDownloadForm = document.getElementById('downloadForm');
        if (newDownloadForm && currentDownloadForm) {
            DOWNLOAD_FIELD_NAMES.forEach(function (fieldName) {
                const newInput = newDownloadForm.querySelector(`input[name="${fieldName}"]`);
                const currentInput = currentDownloadForm.querySelector(`input[name="${fieldName}"]`);
                if (newInput && currentInput) {
                    currentInput.value = newInput.value;
                }
            });
        }
    }

    /*
     * Attaches the submit-event listener on #reportForm so the
     * Generate Report flow runs via fetch instead of triggering a
     * full page navigation. #downloadForm is intentionally left
     * untouched: when the Download PDF button is clicked, the
     * browser submits #downloadForm to /download-pdf natively, and
     * Flask's send_file response (with Content-Disposition:
     * attachment; filename="{name}_Report.pdf") triggers the native
     * file save dialog.
     */
    function init() {
        const reportForm = document.getElementById('reportForm');
        if (reportForm) {
            reportForm.addEventListener('submit', function (event) {
                event.preventDefault();
                submitReportForm();
            });
        }
    }

    /*
     * Public global exposed on window so the inline
     * onclick="generateReport()" attribute on the Generate Report
     * button in templates/index.html resolves. The template invokes
     * the function with NO arguments, so `event` is undefined and
     * this body is a no-op; the actual fetch is started by the
     * submit-event listener attached in init() after the browser
     * proceeds to submit #reportForm. If a future change passes the
     * click event explicitly, the guarded branch calls
     * preventDefault and starts the fetch directly.
     */
    window.generateReport = function (event) {
        if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
            submitReportForm();
        }
    };

    /*
     * Public global exposed on window so the inline
     * onclick="downloadPDF()" attribute on the Download PDF button
     * in templates/index.html resolves. Intentionally empty: the
     * Download PDF button is type="submit" form="downloadForm", so
     * the browser submits the hidden download form to /download-pdf
     * natively after this handler returns. The server response is a
     * PDF binary with a Content-Disposition: attachment header that
     * the browser then saves as "{name}_Report.pdf", reproducing
     * the original jsPDF doc.save() user experience.
     */
    window.downloadPDF = function (event) {
        // Intentionally empty - browser handles the form submission.
        void event;
    };

    /*
     * Bootstrap. The <script> tag is loaded at the END of <body>
     * in templates/index.html, so document.readyState is typically
     * 'interactive' or 'complete' when this code runs and init()
     * can be called synchronously. The readyState check guards
     * against future placements (e.g. moving the tag into <head>)
     * where DOMContentLoaded has not yet fired.
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
