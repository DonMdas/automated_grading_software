# OCR Code Module for Automated Grading

This module provides tools to extract text from PDF documents, specifically for an automated grading system. It can process both teacher's answer keys and student's answer sheets using Optical Character Recognition (OCR).

## Author

- Satwik Kotta

## Description

This module contains two main scripts:

-   `extract_answer_key.py`: This script is designed to parse a PDF document containing an answer key. It identifies question numbers, the questions themselves, and their corresponding answers, then exports them into a structured JSON file.
-   `studentanswer.py`: This script processes a student's submitted answer sheet in PDF format. It uses an "anchor and slice" method to robustly find and extract each numbered answer, saving the results to a JSON file.

## Requirements

### Python Libraries

You need to install the following Python libraries. You can install them using pip:

```bash
pip install pdf2image pytesseract Pillow
```

### System Dependencies

This module relies on two external programs that must be installed on your system and available in your system's PATH.

1.  **Poppler**: A PDF rendering library, required by `pdf2image`.
2.  **Tesseract OCR Engine**: Google's OCR engine, required by `pytesseract`.

Please follow the installation instructions for your specific operating system to install these dependencies.

## Usage

To use the functionality of this module, you can import the functions into your own Python scripts.

### `extract_answer_key.py`

This script provides the `extract_answer_key_to_json` function.

```python
from extract_answer_key import extract_answer_key_to_json

pdf_path = 'path/to/your/answer_key.pdf'
output_path = 'path/to/save/answer_key.json'

extract_answer_key_to_json(pdf_path, output_path)
```

### `studentanswer.py`

This script provides the `extract_student_answers_to_json` function.

```python
from studentanswer import extract_student_answers_to_json

pdf_path = 'path/to/your/student_submission.pdf'
output_path = 'path/to/save/student_answers.json'

extract_student_answers_to_json(pdf_path, output_path)
```
