"""
File handling utilities for the medical pricing application.
"""

import json
import csv
from pathlib import Path
from typing import Dict, Any, List, Union, Optional
import logging
from datetime import datetime

from ..extractors import SimpleExtractor
try:
    from ..extractors import PDFExtractor, OCRExtractor
    PDF_OCR_AVAILABLE = True
except ImportError:
    PDFExtractor = None
    OCRExtractor = None
    PDF_OCR_AVAILABLE = False
from ..pricing.models import MedicalData, PricingResult


class FileHandler:
    """Handle file operations for input and output."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize file handler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize extractors
        extractor_config = config.get('simple_extractor', {}) if config else {}
        self.simple_extractor = SimpleExtractor(extractor_config)
        
        if PDF_OCR_AVAILABLE and PDFExtractor is not None and OCRExtractor is not None:
            pdf_config = config.get('pdf_extractor', {}) if config else {}
            ocr_config = config.get('ocr_extractor', {}) if config else {}
            self.pdf_extractor = PDFExtractor(pdf_config)
            self.ocr_extractor = OCRExtractor(ocr_config)
        else:
            self.pdf_extractor = None
            self.ocr_extractor = None
            self.logger.warning("PDF/OCR extractors not available - only text files will be supported")
        
        # Output directory
        output_dir_name = config.get('output_dir', 'output') if config else 'output'
        self.output_dir = Path(output_dir_name)
        self.output_dir.mkdir(exist_ok=True)
    
    def process_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Process a single file and extract medical data.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Dictionary with processing results
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            self.logger.error(error_msg)
            return {'error': error_msg}
        
        self.logger.info(f"Processing file: {file_path}")
        
        try:
            # Determine which extractor to use
            if self.pdf_extractor and self.pdf_extractor.can_handle(file_path):
                # Try PDF extractor first
                result = self.pdf_extractor.extract(file_path)
                
                # If PDF extraction has low confidence and OCR can handle it, try OCR
                if (self.ocr_extractor and 'medical_data' in result and 
                    result['medical_data'].confidence_score < 50 and
                    self.ocr_extractor.can_handle(file_path)):
                    
                    self.logger.info("PDF extraction had low confidence, trying OCR")
                    ocr_result = self.ocr_extractor.extract(file_path)
                    
                    # Use OCR result if it has higher confidence
                    if ('medical_data' in ocr_result and
                        ocr_result['medical_data'].confidence_score > result['medical_data'].confidence_score):
                        result = ocr_result
                        
            elif self.ocr_extractor and self.ocr_extractor.can_handle(file_path):
                result = self.ocr_extractor.extract(file_path)
            elif self.simple_extractor.can_handle(file_path):
                result = self.simple_extractor.extract(file_path)
            else:
                error_msg = f"Unsupported file type: {file_path.suffix}"
                self.logger.error(error_msg)
                return {'error': error_msg}
            
            # Add processing metadata
            result['processed_at'] = datetime.now().isoformat()
            result['file_name'] = file_path.name
            result['file_size'] = file_path.stat().st_size
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing {file_path}: {str(e)}"
            self.logger.error(error_msg)
            return {'error': error_msg}
    
    def process_directory(self, directory_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Process all supported files in a directory.
        
        Args:
            directory_path: Path to directory containing files
            
        Returns:
            List of processing results
        """
        directory_path = Path(directory_path)
        
        if not directory_path.exists() or not directory_path.is_dir():
            error_msg = f"Directory not found or not a directory: {directory_path}"
            self.logger.error(error_msg)
            return [{'error': error_msg}]
        
        self.logger.info(f"Processing directory: {directory_path}")
        
        # Get all supported files
        supported_extensions = set(self.simple_extractor.get_supported_extensions())
        
        if self.pdf_extractor:
            supported_extensions.update(self.pdf_extractor.get_supported_extensions())
        if self.ocr_extractor:
            supported_extensions.update(self.ocr_extractor.get_supported_extensions())
        
        files = []
        for ext in supported_extensions:
            files.extend(directory_path.glob(f"*{ext}"))
            files.extend(directory_path.glob(f"*{ext.upper()}"))  # Case insensitive
        
        if not files:
            warning_msg = f"No supported files found in {directory_path}"
            self.logger.warning(warning_msg)
            return [{'warning': warning_msg}]
        
        results = []
        for file_path in sorted(files):
            result = self.process_file(file_path)
            results.append(result)
        
        self.logger.info(f"Processed {len(files)} files from {directory_path}")
        return results
    
    def save_results(self, results: Union[Dict[str, Any], List[Dict[str, Any]]], 
                    output_file: Optional[str] = None) -> Path:
        """
        Save processing results to file.
        
        Args:
            results: Results to save (single result or list of results)
            output_file: Output file name (if None, generates timestamp-based name)
            
        Returns:
            Path to saved file
        """
        if not isinstance(results, list):
            results = [results]
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"gmpricing_results_{timestamp}.json"
        
        output_path = self.output_dir / output_file
        
        try:
            # Convert results to JSON-serializable format
            serializable_results = self._make_serializable(results)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_results, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved results to: {output_path}")
            return output_path
            
        except Exception as e:
            error_msg = f"Error saving results: {str(e)}"
            self.logger.error(error_msg)
            raise
    
    def save_pricing_results(self, pricing_results: List[PricingResult], 
                           output_file: Optional[str] = None) -> Path:
        """
        Save pricing results to CSV file.
        
        Args:
            pricing_results: List of pricing results
            output_file: Output file name
            
        Returns:
            Path to saved file
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"pricing_results_{timestamp}.csv"
        
        output_path = self.output_dir / output_file
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    'Base Price', 'Insurance Adjustment', 'Final Price',
                    'Procedure Costs', 'Confidence Level', 'Calculation Date',
                    'Notes', 'Warnings'
                ])
                
                # Write data
                for result in pricing_results:
                    writer.writerow([
                        f"${result.base_price:.2f}",
                        f"${result.insurance_adjustment:.2f}",
                        f"${result.final_price:.2f}",
                        '; '.join(f"{k}: ${v:.2f}" for k, v in result.procedure_costs.items()),
                        f"{result.confidence_level:.1f}%",
                        result.calculation_date.strftime("%Y-%m-%d %H:%M:%S"),
                        '; '.join(result.notes),
                        '; '.join(result.warnings)
                    ])
            
            self.logger.info(f"Saved pricing results to: {output_path}")
            return output_path
            
        except Exception as e:
            error_msg = f"Error saving pricing results: {str(e)}"
            self.logger.error(error_msg)
            raise
    
    def _make_serializable(self, obj: Any) -> Any:
        """
        Convert objects to JSON-serializable format.
        
        Args:
            obj: Object to convert
            
        Returns:
            JSON-serializable object
        """
        if isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (MedicalData, PricingResult)):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            else:
                return obj.__dict__
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        else:
            try:
                json.dumps(obj)  # Test if serializable
                return obj
            except (TypeError, ValueError):
                return str(obj)
    
    def load_results(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """
        Load previously saved results.
        
        Args:
            file_path: Path to results file
            
        Returns:
            List of loaded results
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            error_msg = f"Results file not found: {file_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            self.logger.info(f"Loaded results from: {file_path}")
            return results
            
        except Exception as e:
            error_msg = f"Error loading results: {str(e)}"
            self.logger.error(error_msg)
            raise
    
    def get_supported_file_types(self) -> List[str]:
        """
        Get list of all supported file types.
        
        Returns:
            List of supported file extensions
        """
        supported = list(self.simple_extractor.get_supported_extensions())
        
        if self.pdf_extractor:
            supported.extend(self.pdf_extractor.get_supported_extensions())
        if self.ocr_extractor:
            supported.extend(self.ocr_extractor.get_supported_extensions())
            
        return list(set(supported))
    
    def create_sample_data(self, output_dir: Optional[Path] = None) -> Path:
        """
        Create sample medical data files for testing.
        
        Args:
            output_dir: Directory to create sample files in
            
        Returns:
            Path to sample data directory
        """
        if output_dir is None:
            output_dir = Path("sample_data")
        
        output_dir.mkdir(exist_ok=True)
        
        # Create sample medical report text
        sample_text = """
MEDICAL REPORT

Patient ID: MRN123456
Patient Name: John Smith
Age: 45 years old
Date of Service: 03/15/2024

DIAGNOSIS:
- Essential hypertension (I10)
- Type 2 diabetes mellitus (E11.9)

PROCEDURES PERFORMED:
- Office visit, established patient (99213)
- Blood pressure check
- Diabetes monitoring

INSURANCE:
Insurance Type: Private Insurance (Aetna)
Coverage: 85% covered

BILLING:
Procedure Code: 99213
Estimated Cost: $175.00

Provider: Dr. Jane Medical
Facility: General Medical Center
        """.strip()
        
        # Save sample text file
        sample_file = output_dir / "sample_medical_report.txt"
        with open(sample_file, 'w', encoding='utf-8') as f:
            f.write(sample_text)
        
        self.logger.info(f"Created sample data in: {output_dir}")
        return output_dir