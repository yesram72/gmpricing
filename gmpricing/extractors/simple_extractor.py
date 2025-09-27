"""
Simple text extractor that works without heavy dependencies.
This is a fallback for when PDF and OCR libraries are not available.
"""

import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from .base_extractor import BaseExtractor
from ..pricing.models import MedicalData, ProcedureType, InsuranceType


class SimpleExtractor(BaseExtractor):
    """Simple text extractor for basic text files."""
    
    def can_handle(self, file_path: Path) -> bool:
        """Check if this extractor can handle text files."""
        return file_path.suffix.lower() in ['.txt', '.text']
    
    def get_supported_extensions(self) -> List[str]:
        """Return supported file extensions."""
        return ['.txt', '.text']
    
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract data from text file.
        
        Args:
            file_path: Path to text file
            
        Returns:
            Dictionary containing extracted medical data
        """
        if not self.validate_file(file_path):
            return {'error': 'Invalid file'}
        
        try:
            # Read text file
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text.strip():
                self.logger.warning(f"No text found in {file_path}")
                return {'error': 'No text found in file'}
            
            # Parse the text
            medical_data = self._parse_medical_text(text)
            
            return {
                'medical_data': medical_data,
                'raw_text': text,
                'extraction_method': 'simple_text',
                'file_path': str(file_path)
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting from {file_path}: {str(e)}")
            return {'error': str(e)}
    
    def _parse_medical_text(self, text: str) -> MedicalData:
        """
        Parse extracted text to identify medical information.
        This is the same logic as in PDFExtractor but works with plain text.
        """
        medical_data = MedicalData(raw_text=text)
        
        # Extract patient information
        medical_data.patient_id = self._extract_patient_id(text)
        medical_data.patient_name = self._extract_patient_name(text)
        medical_data.age = self._extract_age(text)
        
        # Extract medical codes
        medical_data.procedure_codes = self._extract_procedure_codes(text)
        medical_data.diagnosis_codes = self._extract_diagnosis_codes(text)
        
        # Extract dates
        medical_data.service_date = self._extract_service_date(text)
        
        # Extract insurance information
        medical_data.insurance_type = self._extract_insurance_type(text)
        medical_data.insurance_coverage = self._extract_insurance_coverage(text)
        
        # Determine procedure type
        medical_data.procedure_type = self._determine_procedure_type(text, medical_data.procedure_codes)
        
        # Calculate confidence score
        medical_data.confidence_score = self._calculate_confidence(medical_data)
        
        return medical_data
    
    def _extract_patient_id(self, text: str) -> str:
        """Extract patient ID from text."""
        patterns = [
            r'Patient\s+ID[:\s]+([A-Z0-9]+)',
            r'ID[:\s]+([A-Z0-9]+)',
            r'Patient\s+Number[:\s]+([A-Z0-9]+)',
            r'MRN[:\s]+([A-Z0-9]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_patient_name(self, text: str) -> str:
        """Extract patient name from text."""
        patterns = [
            r'Patient[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Name[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'Patient\s+Name[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_age(self, text: str) -> int:
        """Extract patient age from text."""
        patterns = [
            r'Age[:\s]+(\d+)',
            r'(\d+)\s+years?\s+old',
            r'DOB[:\s]+\d{1,2}[/-]\d{1,2}[/-](\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if 'DOB' in pattern:
                    birth_year = int(match.group(1))
                    current_year = datetime.now().year
                    return current_year - birth_year
                else:
                    return int(match.group(1))
        return None
    
    def _extract_procedure_codes(self, text: str) -> List[str]:
        """Extract CPT/procedure codes from text."""
        cpt_pattern = r'\b\d{5}\b'
        codes = re.findall(cpt_pattern, text)
        
        valid_codes = []
        for code in codes:
            if 100 <= int(code) <= 99999:
                valid_codes.append(code)
        
        return list(set(valid_codes))
    
    def _extract_diagnosis_codes(self, text: str) -> List[str]:
        """Extract ICD diagnosis codes from text."""
        icd10_pattern = r'\b[A-Z]\d{2}(?:\.\d+)?\b'
        codes = re.findall(icd10_pattern, text)
        return list(set(codes))
    
    def _extract_service_date(self, text: str) -> datetime:
        """Extract service date from text."""
        date_patterns = [
            r'Service\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'Date\s+of\s+Service[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y', '%d-%m-%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                except ValueError:
                    continue
        return None
    
    def _extract_insurance_type(self, text: str) -> InsuranceType:
        """Extract insurance type from text."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['medicare', 'medicaid', 'government', 'public']):
            return InsuranceType.PUBLIC
        elif any(word in text_lower for word in ['private', 'aetna', 'blue cross', 'cigna', 'humana']):
            return InsuranceType.PRIVATE
        elif any(word in text_lower for word in ['self pay', 'self-pay', 'cash', 'uninsured']):
            return InsuranceType.SELF_PAY
        
        return None
    
    def _extract_insurance_coverage(self, text: str) -> float:
        """Extract insurance coverage percentage from text."""
        patterns = [
            r'Coverage[:\s]+(\d+)%',
            r'(\d+)%\s+covered',
            r'Insurance\s+pays[:\s]+(\d+)%'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None
    
    def _determine_procedure_type(self, text: str, procedure_codes: List[str]) -> ProcedureType:
        """Determine procedure type based on text content and codes."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['surgery', 'surgical', 'operation', 'procedure']):
            return ProcedureType.SURGERY
        elif any(word in text_lower for word in ['emergency', 'urgent', 'trauma', 'er', 'emergency room']):
            return ProcedureType.EMERGENCY
        elif any(word in text_lower for word in ['x-ray', 'mri', 'ct scan', 'ultrasound', 'diagnostic']):
            return ProcedureType.DIAGNOSTIC
        elif any(word in text_lower for word in ['consultation', 'visit', 'appointment', 'exam']):
            return ProcedureType.CONSULTATION
        
        return ProcedureType.TREATMENT
    
    def _calculate_confidence(self, medical_data: MedicalData) -> float:
        """Calculate confidence score based on extracted data completeness."""
        score = 0.0
        total_fields = 10
        
        if medical_data.patient_id:
            score += 1
        if medical_data.patient_name:
            score += 1
        if medical_data.age:
            score += 1
        if medical_data.procedure_codes:
            score += 2
        if medical_data.diagnosis_codes:
            score += 2
        if medical_data.service_date:
            score += 1
        if medical_data.insurance_type:
            score += 1
        if medical_data.procedure_type:
            score += 1
        
        return (score / total_fields) * 100