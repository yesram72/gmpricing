"""
Data validation utilities for medical pricing application.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from ..pricing.models import MedicalData, PricingResult


class DataValidator:
    """Validate extracted medical data and pricing results."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize validator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Validation rules
        self.min_confidence = config.get('min_confidence', 30.0)
        self.require_patient_id = config.get('require_patient_id', False)
        self.require_procedure_codes = config.get('require_procedure_codes', True)
        self.max_age = config.get('max_age', 150)
        self.min_age = config.get('min_age', 0)
    
    def validate_medical_data(self, medical_data: MedicalData) -> Tuple[bool, List[str]]:
        """
        Validate extracted medical data.
        
        Args:
            medical_data: Medical data to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check confidence score
        if medical_data.confidence_score < self.min_confidence:
            errors.append(f"Confidence score too low: {medical_data.confidence_score:.1f}% "
                         f"(minimum: {self.min_confidence:.1f}%)")
        
        # Validate patient ID if required
        if self.require_patient_id and not medical_data.patient_id:
            errors.append("Patient ID is required but not found")
        
        # Validate patient ID format if present
        if medical_data.patient_id and not self._is_valid_patient_id(medical_data.patient_id):
            errors.append(f"Invalid patient ID format: {medical_data.patient_id}")
        
        # Validate patient name
        if medical_data.patient_name and not self._is_valid_name(medical_data.patient_name):
            errors.append(f"Invalid patient name format: {medical_data.patient_name}")
        
        # Validate age
        if medical_data.age is not None:
            if not self.min_age <= medical_data.age <= self.max_age:
                errors.append(f"Invalid age: {medical_data.age} "
                             f"(must be between {self.min_age} and {self.max_age})")
        
        # Validate procedure codes if required
        if self.require_procedure_codes and not medical_data.procedure_codes:
            errors.append("Procedure codes are required but not found")
        
        # Validate procedure code formats
        for code in medical_data.procedure_codes:
            if not self._is_valid_procedure_code(code):
                errors.append(f"Invalid procedure code format: {code}")
        
        # Validate diagnosis codes
        for code in medical_data.diagnosis_codes:
            if not self._is_valid_diagnosis_code(code):
                errors.append(f"Invalid diagnosis code format: {code}")
        
        # Validate dates
        if medical_data.service_date and medical_data.service_date > datetime.now():
            errors.append("Service date cannot be in the future")
        
        if (medical_data.admission_date and medical_data.discharge_date and
            medical_data.admission_date > medical_data.discharge_date):
            errors.append("Admission date cannot be after discharge date")
        
        # Validate insurance coverage
        if medical_data.insurance_coverage is not None:
            if not 0 <= medical_data.insurance_coverage <= 100:
                errors.append(f"Invalid insurance coverage: {medical_data.insurance_coverage}% "
                             "(must be between 0% and 100%)")
        
        return len(errors) == 0, errors
    
    def validate_pricing_result(self, pricing_result: PricingResult) -> Tuple[bool, List[str]]:
        """
        Validate pricing calculation result.
        
        Args:
            pricing_result: Pricing result to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for negative prices
        if pricing_result.base_price < 0:
            errors.append(f"Base price cannot be negative: ${pricing_result.base_price:.2f}")
        
        if pricing_result.final_price < 0:
            errors.append(f"Final price cannot be negative: ${pricing_result.final_price:.2f}")
        
        # Check for unreasonably high prices
        max_reasonable_price = 100000.00  # $100,000
        if pricing_result.base_price > max_reasonable_price:
            errors.append(f"Base price seems unreasonably high: ${pricing_result.base_price:.2f}")
        
        if pricing_result.final_price > max_reasonable_price:
            errors.append(f"Final price seems unreasonably high: ${pricing_result.final_price:.2f}")
        
        # Validate confidence level
        if not 0 <= pricing_result.confidence_level <= 100:
            errors.append(f"Invalid confidence level: {pricing_result.confidence_level}% "
                         "(must be between 0% and 100%)")
        
        # Check procedure costs
        for code, cost in pricing_result.procedure_costs.items():
            if cost < 0:
                errors.append(f"Procedure cost cannot be negative: {code} = ${cost:.2f}")
            if cost > max_reasonable_price:
                errors.append(f"Procedure cost seems unreasonably high: {code} = ${cost:.2f}")
        
        # Validate calculation date
        if pricing_result.calculation_date > datetime.now():
            errors.append("Calculation date cannot be in the future")
        
        return len(errors) == 0, errors
    
    def _is_valid_patient_id(self, patient_id: str) -> bool:
        """
        Validate patient ID format.
        
        Args:
            patient_id: Patient ID to validate
            
        Returns:
            True if valid format
        """
        if not patient_id or len(patient_id) < 3:
            return False
        
        # Allow alphanumeric characters and common separators
        pattern = r'^[A-Z0-9\-_]{3,20}$'
        return bool(re.match(pattern, patient_id.upper()))
    
    def _is_valid_name(self, name: str) -> bool:
        """
        Validate patient name format.
        
        Args:
            name: Name to validate
            
        Returns:
            True if valid format
        """
        if not name or len(name) < 2:
            return False
        
        # Allow letters, spaces, hyphens, apostrophes
        pattern = r"^[A-Za-z\s\-'\.]{2,50}$"
        return bool(re.match(pattern, name))
    
    def _is_valid_procedure_code(self, code: str) -> bool:
        """
        Validate procedure code format (CPT codes).
        
        Args:
            code: Procedure code to validate
            
        Returns:
            True if valid format
        """
        if not code:
            return False
        
        # CPT codes are typically 5-digit numbers
        if re.match(r'^\d{5}$', code):
            code_num = int(code)
            # CPT codes range from 00100 to 99999
            return 100 <= code_num <= 99999
        
        # Also allow HCPCS codes (letter followed by 4 digits)
        if re.match(r'^[A-Z]\d{4}$', code):
            return True
        
        return False
    
    def _is_valid_diagnosis_code(self, code: str) -> bool:
        """
        Validate diagnosis code format (ICD-10 codes).
        
        Args:
            code: Diagnosis code to validate
            
        Returns:
            True if valid format
        """
        if not code:
            return False
        
        # ICD-10 codes: letter + 2 digits + optional dot + optional additional digits
        pattern = r'^[A-Z]\d{2}(?:\.\d{1,4})?$'
        return bool(re.match(pattern, code.upper()))
    
    def validate_extraction_result(self, result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate extraction result from file processing.
        
        Args:
            result: Extraction result dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        warnings = []
        
        # Check for extraction errors
        if 'error' in result:
            errors.append(f"Extraction error: {result['error']}")
            return False, errors
        
        # Check for required fields
        if 'medical_data' not in result:
            errors.append("Missing medical data in extraction result")
            return False, errors
        
        # Validate medical data
        medical_data = result['medical_data']
        if isinstance(medical_data, dict):
            # Convert dict to MedicalData object for validation
            try:
                medical_data = MedicalData(**medical_data)
            except Exception as e:
                errors.append(f"Invalid medical data format: {str(e)}")
                return False, errors
        
        is_valid, validation_errors = self.validate_medical_data(medical_data)
        errors.extend(validation_errors)
        
        # Check extraction quality indicators
        if 'raw_text' in result:
            text_length = len(result['raw_text'])
            if text_length < 50:
                warnings.append(f"Very short extracted text ({text_length} characters)")
            elif text_length > 50000:
                warnings.append(f"Very long extracted text ({text_length} characters)")
        
        # Check extraction method confidence
        if result.get('extraction_method') == 'ocr':
            ocr_confidence = result.get('ocr_confidence', 0)
            if ocr_confidence < 60:
                warnings.append(f"Low OCR confidence: {ocr_confidence:.1f}%")
        
        # Add warnings to result if any
        if warnings:
            result.setdefault('warnings', []).extend(warnings)
        
        return is_valid, errors
    
    def generate_validation_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a validation report for multiple results.
        
        Args:
            results: List of extraction results
            
        Returns:
            Validation report dictionary
        """
        report = {
            'total_files': len(results),
            'valid_files': 0,
            'invalid_files': 0,
            'warnings': 0,
            'errors': [],
            'summary': {},
            'details': []
        }
        
        confidence_scores = []
        extraction_methods = {}
        
        for i, result in enumerate(results):
            file_name = result.get('file_name', f'File_{i+1}')
            is_valid, errors = self.validate_extraction_result(result)
            
            detail = {
                'file_name': file_name,
                'valid': is_valid,
                'errors': errors,
                'warnings': result.get('warnings', [])
            }
            
            if is_valid:
                report['valid_files'] += 1
                
                # Collect statistics
                if 'medical_data' in result:
                    medical_data = result['medical_data']
                    if hasattr(medical_data, 'confidence_score'):
                        confidence_scores.append(medical_data.confidence_score)
                    elif isinstance(medical_data, dict) and 'confidence_score' in medical_data:
                        confidence_scores.append(medical_data['confidence_score'])
                
                extraction_method = result.get('extraction_method', 'unknown')
                extraction_methods[extraction_method] = extraction_methods.get(extraction_method, 0) + 1
            else:
                report['invalid_files'] += 1
                report['errors'].extend(errors)
            
            if result.get('warnings'):
                report['warnings'] += len(result['warnings'])
            
            report['details'].append(detail)
        
        # Generate summary statistics
        if confidence_scores:
            report['summary']['avg_confidence'] = sum(confidence_scores) / len(confidence_scores)
            report['summary']['min_confidence'] = min(confidence_scores)
            report['summary']['max_confidence'] = max(confidence_scores)
        
        report['summary']['extraction_methods'] = extraction_methods
        report['summary']['success_rate'] = (report['valid_files'] / report['total_files']) * 100 if report['total_files'] > 0 else 0
        
        return report