"""
OCR extractor for scanned PDFs and image files.
"""

from pathlib import Path
from typing import Dict, Any, List
import pytesseract
from PIL import Image
import pdf2image
import logging

from .pdf_extractor import PDFExtractor
from ..pricing.models import MedicalData


class OCRExtractor(PDFExtractor):
    """Extractor for scanned PDFs and image files using OCR."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.dpi = config.get('dpi', 300) if config else 300
        self.lang = config.get('language', 'eng') if config else 'eng'
        
        # Configure tesseract if path is provided
        tesseract_cmd = config.get('tesseract_cmd') if config else None
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if this extractor can handle the file type."""
        supported_extensions = self.get_supported_extensions()
        return file_path.suffix.lower() in supported_extensions
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif']
    
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract data from scanned document using OCR.
        
        Args:
            file_path: Path to the file (PDF or image)
            
        Returns:
            Dictionary containing extracted medical data
        """
        if not self.validate_file(file_path):
            return {'error': 'Invalid file'}
        
        try:
            # First try regular PDF extraction
            if file_path.suffix.lower() == '.pdf':
                pdf_result = super().extract(file_path)
                
                # If PDF extraction was successful and found meaningful text, use it
                if 'medical_data' in pdf_result and pdf_result['medical_data'].confidence_score > 30:
                    self.logger.info(f"Using text-based PDF extraction for {file_path}")
                    return pdf_result
                
                # Otherwise, proceed with OCR
                self.logger.info(f"Text-based extraction failed, using OCR for {file_path}")
                text = self._extract_text_from_pdf_ocr(file_path)
            else:
                # Image file - use OCR directly
                text = self._extract_text_from_image(file_path)
            
            if not text.strip():
                self.logger.warning(f"No text extracted via OCR from {file_path}")
                return {'error': 'No text found in document'}
            
            # Parse the extracted text using parent class method
            medical_data = self._parse_medical_text(text)
            
            return {
                'medical_data': medical_data,
                'raw_text': text,
                'extraction_method': 'ocr',
                'file_path': str(file_path),
                'ocr_confidence': self._calculate_ocr_confidence(text)
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting from {file_path}: {str(e)}")
            return {'error': str(e)}
    
    def _extract_text_from_pdf_ocr(self, file_path: Path) -> str:
        """
        Extract text from PDF using OCR (for scanned PDFs).
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        try:
            # Convert PDF pages to images
            images = pdf2image.convert_from_path(
                file_path,
                dpi=self.dpi,
                first_page=1,
                last_page=None  # Process all pages
            )
            
            text = ""
            for i, image in enumerate(images):
                self.logger.debug(f"Processing page {i+1} of {file_path}")
                
                # Perform OCR on the image
                page_text = pytesseract.image_to_string(
                    image,
                    lang=self.lang,
                    config='--psm 6'  # Uniform block of text
                )
                
                if page_text.strip():
                    text += f"--- Page {i+1} ---\n{page_text}\n"
            
            return text
            
        except Exception as e:
            self.logger.error(f"Error converting PDF to images: {str(e)}")
            raise
    
    def _extract_text_from_image(self, file_path: Path) -> str:
        """
        Extract text from image file using OCR.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Extracted text
        """
        try:
            # Open and preprocess image
            image = Image.open(file_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance image for better OCR results
            image = self._preprocess_image(image)
            
            # Perform OCR
            text = pytesseract.image_to_string(
                image,
                lang=self.lang,
                config='--psm 6'  # Uniform block of text
            )
            
            return text
            
        except Exception as e:
            self.logger.error(f"Error processing image {file_path}: {str(e)}")
            raise
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR accuracy.
        
        Args:
            image: PIL Image object
            
        Returns:
            Preprocessed image
        """
        try:
            from PIL import ImageEnhance, ImageFilter
            
            # Resize image if it's too small (minimum 300 DPI equivalent)
            width, height = image.size
            if width < 1200 or height < 1200:
                scale_factor = max(1200 / width, 1200 / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Apply slight noise reduction
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            return image
            
        except ImportError:
            # If PIL enhancement modules are not available, return original image
            self.logger.warning("PIL enhancement modules not available, using original image")
            return image
        except Exception as e:
            self.logger.warning(f"Error preprocessing image: {str(e)}, using original")
            return image
    
    def _calculate_ocr_confidence(self, text: str) -> float:
        """
        Calculate OCR confidence based on text characteristics.
        
        Args:
            text: Extracted text
            
        Returns:
            Confidence score (0-100)
        """
        if not text.strip():
            return 0.0
        
        # Basic heuristics for OCR quality
        score = 50.0  # Base score
        
        # Check for common OCR artifacts that indicate poor quality
        artifacts = ['|||', '~~~', '```', 'lll', '|||']
        artifact_count = sum(text.count(artifact) for artifact in artifacts)
        score -= min(artifact_count * 10, 30)
        
        # Check for reasonable word-to-character ratio
        words = text.split()
        if words:
            avg_word_length = sum(len(word) for word in words) / len(words)
            if 2 <= avg_word_length <= 12:  # Reasonable average word length
                score += 10
        
        # Check for presence of numbers (medical documents often have codes, dates)
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            score += min(len(numbers), 20)
        
        # Check for proper capitalization patterns
        lines = text.split('\n')
        proper_lines = sum(1 for line in lines if line and line[0].isupper())
        if lines:
            capitalization_ratio = proper_lines / len(lines)
            if capitalization_ratio > 0.3:
                score += 10
        
        return min(score, 100.0)
    
    def get_ocr_data(self, file_path: Path) -> Dict[str, Any]:
        """
        Get detailed OCR data including confidence scores.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with OCR details
        """
        if not self.validate_file(file_path):
            return {'error': 'Invalid file'}
        
        try:
            if file_path.suffix.lower() == '.pdf':
                images = pdf2image.convert_from_path(file_path, dpi=self.dpi)
                image = images[0]  # Use first page for confidence calculation
            else:
                image = Image.open(file_path)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image = self._preprocess_image(image)
            
            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'avg_confidence': avg_confidence,
                'word_count': len([word for word in ocr_data['text'] if word.strip()]),
                'page_confidence': confidences,
                'text_length': len(' '.join(ocr_data['text']))
            }
            
        except Exception as e:
            self.logger.error(f"Error getting OCR data from {file_path}: {str(e)}")
            return {'error': str(e)}