from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract, re, json

def extract_answer_key_to_json(pdf_path, output_path):
    images = convert_from_path(pdf_path, dpi=400)
    full_text = ''
    for img in images:
        img = img.convert('L')
        img = img.filter(ImageFilter.SHARPEN)
        img = ImageEnhance.Contrast(img).enhance(2.0)
        full_text += '\n' + pytesseract.image_to_string(img, lang='eng')

    pattern = re.compile(r'(?:Q?\s?(\d+)[\).:\-]?)\s*([^\n]+)[\n\r]+([\s\S]*?)(?=Q?\s?\d+[\).:\-]|$)', re.IGNORECASE)
    out = {}
    for qno, question, answer in pattern.findall(full_text):
        qno = qno.strip()
        question = ' '.join(question.strip().split())
        answer = ' '.join(answer.strip().split())
        if question and answer:
            out[qno] = { 'question': question, 'answer': answer }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f'✅ Answer key saved to: {output_path}')
