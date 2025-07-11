from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import re
import json
import os

def extract_student_answers_to_json(pdf_path, output_path):
    # Convert PDF to images
    images = convert_from_path(pdf_path, dpi=400)
    full_text = ''
    for img in images:
        # Preprocessing
        img = img.convert('L')  # Convert to grayscale
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2.0)

        # OCR
        text = pytesseract.image_to_string(img, lang='eng')
        full_text += '\n' + text

    # Regex to extract question numbers and answers
    pattern = re.compile(
        r'(?:^|\n)\s*(\d{1,2})[\).:-]?\s+(.*?)(?=\n\s*\d{1,2}[\).:-]?\s+|$)', 
        re.DOTALL
    )
    matches = pattern.findall(full_text)

    # Build JSON
    output = {}
    for qno, ans in matches:
        qno = qno.strip()
        ans = ' '.join(ans.strip().split())
        output[qno] = ans

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f'✅ Student answers saved to: {output_path}')

# ---- Change these paths to match your system ----
pdf_path = '/Users/satwik/Downloads/jeff1dd/Answers.pdf'
output_path = '/Users/satwik/Downloads/jeff1dd/ocr_student_answers.json'

if __name__ == '__main__':
    extract_student_answers_to_json(pdf_path, output_path)
