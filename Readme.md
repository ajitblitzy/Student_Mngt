# Student Report Generator using JavaScript

## Overview
This project allows users to:
- Enter student details using a form
- Calculate total marks and percentage
- Generate a formatted student report
- Export the report as a PDF file

---

# Project Structure

```text
student-report-generator/
│
├── index.html
├── style.css
├── script.js
└── README.md
```

---

# index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student Report Generator</title>

    <link rel="stylesheet" href="style.css">

    <!-- jsPDF Library -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
</head>
<body>

<div class="container">
    <h1>Student Report Generator</h1>

    <div class="form-section">
        <input type="text" id="studentName" placeholder="Student Name">
        <input type="text" id="rollNumber" placeholder="Roll Number">

        <input type="number" id="maths" placeholder="Maths Marks">
        <input type="number" id="science" placeholder="Science Marks">
        <input type="number" id="english" placeholder="English Marks">
        <input type="number" id="history" placeholder="History Marks">
        <input type="number" id="computer" placeholder="Computer Marks">

        <button onclick="generateReport()">Generate Report</button>
        <button onclick="downloadPDF()">Download PDF</button>
    </div>

    <div id="reportCard" class="report-card">
        <h2>Student Report</h2>

        <p><strong>Name:</strong> <span id="rName"></span></p>
        <p><strong>Roll Number:</strong> <span id="rRoll"></span></p>

        <table>
            <thead>
                <tr>
                    <th>Subject</th>
                    <th>Marks</th>
                </tr>
            </thead>
            <tbody id="marksTable"></tbody>
        </table>

        <p><strong>Total:</strong> <span id="totalMarks"></span></p>
        <p><strong>Percentage:</strong> <span id="percentage"></span>%</p>
        <p><strong>Grade:</strong> <span id="grade"></span></p>
    </div>
</div>

<script src="script.js"></script>

</body>
</html>
```

---

# style.css

```css
body {
    font-family: Arial, sans-serif;
    background: #f4f6f8;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 800px;
    margin: auto;
    background: white;
    padding: 30px;
    border-radius: 10px;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
}

h1, h2 {
    text-align: center;
}

.form-section {
    display: grid;
    gap: 10px;
    margin-bottom: 30px;
}

input {
    padding: 10px;
    font-size: 16px;
}

button {
    padding: 12px;
    background: #007bff;
    color: white;
    border: none;
    cursor: pointer;
    border-radius: 5px;
}

button:hover {
    background: #0056b3;
}

.report-card {
    border-top: 2px solid #ddd;
    padding-top: 20px;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
}

table, th, td {
    border: 1px solid #ccc;
}

th, td {
    padding: 10px;
    text-align: center;
}
```

---

# script.js

```javascript
function generateReport() {
    const name = document.getElementById('studentName').value;
    const roll = document.getElementById('rollNumber').value;

    const subjects = {
        Maths: parseInt(document.getElementById('maths').value || 0),
        Science: parseInt(document.getElementById('science').value || 0),
        English: parseInt(document.getElementById('english').value || 0),
        History: parseInt(document.getElementById('history').value || 0),
        Computer: parseInt(document.getElementById('computer').value || 0)
    };

    let total = 0;

    const tableBody = document.getElementById('marksTable');
    tableBody.innerHTML = '';

    for (let subject in subjects) {
        total += subjects[subject];

        const row = `
            <tr>
                <td>${subject}</td>
                <td>${subjects[subject]}</td>
            </tr>
        `;

        tableBody.innerHTML += row;
    }

    const percentage = (total / 500) * 100;

    let grade = 'F';

    if (percentage >= 90) {
        grade = 'A+';
    } else if (percentage >= 80) {
        grade = 'A';
    } else if (percentage >= 70) {
        grade = 'B';
    } else if (percentage >= 60) {
        grade = 'C';
    } else if (percentage >= 50) {
        grade = 'D';
    }

    document.getElementById('rName').innerText = name;
    document.getElementById('rRoll').innerText = roll;
    document.getElementById('totalMarks').innerText = total;
    document.getElementById('percentage').innerText = percentage.toFixed(2);
    document.getElementById('grade').innerText = grade;
}

function downloadPDF() {
    const { jsPDF } = window.jspdf;

    const doc = new jsPDF();

    const name = document.getElementById('rName').innerText;
    const roll = document.getElementById('rRoll').innerText;
    const total = document.getElementById('totalMarks').innerText;
    const percentage = document.getElementById('percentage').innerText;
    const grade = document.getElementById('grade').innerText;

    doc.setFontSize(18);
    doc.text('Student Report Card', 20, 20);

    doc.setFontSize(12);
    doc.text(`Student Name: ${name}`, 20, 40);
    doc.text(`Roll Number: ${roll}`, 20, 50);
    doc.text(`Total Marks: ${total}`, 20, 60);
    doc.text(`Percentage: ${percentage}%`, 20, 70);
    doc.text(`Grade: ${grade}`, 20, 80);

    doc.save(`${name}_Report.pdf`);
}
```

---

# README.md

```md
# Student Report Generator

## Features

- Enter student details
- Calculate percentage automatically
- Generate grade
- Download report as PDF
- Responsive UI

## Technologies Used

- HTML
- CSS
- JavaScript
- jsPDF

## How to Run

1. Download the project
2. Open `index.html` in browser
3. Enter student details
4. Click Generate Report
5. Click Download PDF
```

---

# Future Enhancements

- Add database support
- Add multiple student report management
- Add charts and analytics
- Add teacher comments
- Add digital signature support
- Export reports to Excel

