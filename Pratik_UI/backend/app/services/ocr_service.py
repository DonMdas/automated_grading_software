import pytesseract
import cv2
import numpy as np
from PIL import Image
import os
from app.core.config import settings

class OCRService:
    def __init__(self):
        # Set tesseract path if specified
        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    
    def extract_text(self, file_path: str) -> str:
        """Extract text from image or PDF file"""
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            return self._extract_from_image(file_path)
        elif file_extension == '.pdf':
            return self._extract_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _extract_from_image(self, image_path: str) -> str:
        """Extract text from image file"""
        
        try:
            # Load image
            image = cv2.imread(image_path)
            
            # Preprocess image for better OCR
            processed_image = self._preprocess_image(image)
            
            # Convert to PIL Image for tesseract
            pil_image = Image.fromarray(processed_image)
            
            # Extract text
            text = pytesseract.image_to_string(pil_image, config='--psm 6')
            
            return self._clean_text(text)
            
        except Exception as e:
            raise Exception(f"OCR failed for image {image_path}: {str(e)}")
    
    def _extract_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Try text extraction first
                page_text = page.get_text()
                
                if page_text.strip():
                    text += page_text + "\n"
                else:
                    # If no text found, use OCR on page image
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("ppm")
                    
                    # Convert to numpy array
                    nparr = np.frombuffer(img_data, np.uint8)
                    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    # Preprocess and OCR
                    processed_image = self._preprocess_image(image)
                    pil_image = Image.fromarray(processed_image)
                    page_text = pytesseract.image_to_string(pil_image, config='--psm 6')
                    
                    text += page_text + "\n"
            
            doc.close()
            return self._clean_text(text)
            
        except Exception as e:
            raise Exception(f"OCR failed for PDF {pdf_path}: {str(e)}")
    
    def _preprocess_image(self, image):
        """Preprocess image for better OCR accuracy"""
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove special characters that might be OCR artifacts
        import re
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)]', '', text)
        
        # Fix common OCR mistakes
        ocr_corrections = {
            '0': 'O',  # Zero to O
            '1': 'I',  # One to I
            '5': 'S',  # Five to S
        }
        
        # Apply corrections cautiously (only for obvious cases)
        for wrong, correct in ocr_corrections.items():
            # Only replace if it's clearly a mistake (surrounded by letters)
            text = re.sub(f'(?<=[a-zA-Z]){wrong}(?=[a-zA-Z])', correct, text)
        
        return text.strip()
    
    def get_confidence_score(self, file_path: str) -> float:
        """Get OCR confidence score for the extracted text"""
        
        try:
            if not os.path.exists(file_path):
                return 0.0
            
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                image = cv2.imread(file_path)
                processed_image = self._preprocess_image(image)
                pil_image = Image.fromarray(processed_image)
                
                # Get detailed OCR data
                data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)
                
                # Calculate average confidence
                confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                
                if confidences:
                    return sum(confidences) / len(confidences)
                else:
                    return 0.0
            
            return 50.0  # Default confidence for PDFs
            
        except Exception:
            return 0.0
