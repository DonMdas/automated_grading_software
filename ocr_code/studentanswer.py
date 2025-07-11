import os
import re
import json
from PIL import Image, ImageEnhance, ImageFilter

# Note: The following libraries must be installed on your system:
# pip install pdf2image pytesseract Pillow
# You also need to install Google's Tesseract OCR engine and Poppler for pdf2image.
from pdf2image import convert_from_path
import pytesseract

def extract_student_answers_to_json(pdf_path, output_path):
    """
    Extracts student answers from a PDF using a robust "anchor and slice" method.

    This function performs the following steps:
    1.  Converts each page of the PDF to a high-resolution image.
    2.  Applies preprocessing filters to each image to improve OCR accuracy.
    3.  Uses Tesseract OCR to extract all text from the images.
    4.  Finds the start of each numbered answer to use as an "anchor".
    5.  Slices the full text between these anchors to isolate each answer.
    6.  Cleans the extracted text and saves it to a structured JSON file.
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Error: The file was not found at '{pdf_path}'")
        return

    print("1. Converting PDF to images...")
    try:
        images = convert_from_path(pdf_path, dpi=400)
    except Exception as e:
        print(f"❌ Error during PDF conversion: {e}")
        print("-> Please ensure 'poppler' is installed and in your system's PATH.")
        return

    full_text = ''
    print(f"2. Found {len(images)} page(s). Starting OCR process...")
    for i, img in enumerate(images):
        # Preprocessing to improve OCR accuracy
        img = img.convert('L')
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        
        # Use pytesseract to extract text, preserving page layout information
        try:
            # The 'psm 6' option helps preserve layout, which can help with line breaks.
            text = pytesseract.image_to_string(img, lang='eng', config='--psm 6')
            full_text += '\n' + text
        except pytesseract.TesseractNotFoundError:
            print("❌ OCR Error: 'tesseract' is not installed or not in your system's PATH.")
            return

    print("3. OCR complete. Raw text extracted. Now parsing answers...")
    # --- New Robust "Anchor and Slice" Logic ---
    
    # This pattern finds the *start* of each answer line (the number and separator).
    # We look for a newline, then spaces, then digits, then a separator.
    pattern = re.compile(r'(?:\n|\A)\s*(\d+)\s*[\).-]')
    
    # `finditer` gives us all matches and their positions (indices) in the text.
    matches = list(pattern.finditer(full_text))
    
    output_data = {}
    if not matches:
        print("❌ Could not find any numbered answers in the document.")
        return

    # Iterate through the matches to slice the text between them.
    for i in range(len(matches)):
        current_match = matches[i]
        
        # The question number is the first captured group.
        q_num = current_match.group(1)
        
        # The answer starts at the end of the current match's pattern.
        start_index = current_match.end()
        
        # The answer ends at the start of the *next* match's pattern.
        # If it's the last match, the answer goes all the way to the end of the text.
        end_index = matches[i+1].start() if i + 1 < len(matches) else len(full_text)
        
        # Slice the full_text to get the raw answer.
        raw_answer = full_text[start_index:end_index]
        
        # Clean the text: remove extra whitespace and newlines.
        cleaned_answer = ' '.join(raw_answer.strip().split())
        
        # Add to dictionary only if the answer is not empty.
        if cleaned_answer:
            output_data[q_num] = {"answer":cleaned_answer}

    print(f"4. Writing {len(output_data)} answers to JSON file...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f'✅ Success! Student answers saved to: {output_path}')


# ---- Change these paths to match your system ----
PDF_FILE_PATH = 'server_data/782918260130/submissions/110290077452225224084.pdf'
JSON_OUTPUT_PATH = r'./student_answers_corrected.json'


if __name__ == '__main__':
    extract_student_answers_to_json(PDF_FILE_PATH, JSON_OUTPUT_PATH)
