"""
Data extraction modules for PDF and image processing.
"""

from .base_extractor import BaseExtractor
from .simple_extractor import SimpleExtractor

# Try to import PDF and OCR extractors, but don't fail if dependencies are missing
try:
    from .pdf_extractor import PDFExtractor
    PDF_AVAILABLE = True
except ImportError:
    PDFExtractor = None
    PDF_AVAILABLE = False

try:
    from .ocr_extractor import OCRExtractor
    OCR_AVAILABLE = True
except ImportError:
    OCRExtractor = None
    OCR_AVAILABLE = False

__all__ = ['BaseExtractor', 'SimpleExtractor']

if PDF_AVAILABLE:
    __all__.append('PDFExtractor')

if OCR_AVAILABLE:
    __all__.append('OCRExtractor')