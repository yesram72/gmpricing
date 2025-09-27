"""
Data models for medical pricing application.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ProcedureType(Enum):
    """Types of medical procedures."""
    CONSULTATION = "consultation"
    SURGERY = "surgery"
    DIAGNOSTIC = "diagnostic"
    TREATMENT = "treatment"
    EMERGENCY = "emergency"


class InsuranceType(Enum):
    """Types of insurance coverage."""
    PRIVATE = "private"
    PUBLIC = "public"
    SELF_PAY = "self_pay"
    MIXED = "mixed"


@dataclass
class MedicalData:
    """Container for extracted medical data."""
    
    # Patient information
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    age: Optional[int] = None
    
    # Medical information
    procedure_codes: List[str] = field(default_factory=list)
    diagnosis_codes: List[str] = field(default_factory=list)
    procedure_type: Optional[ProcedureType] = None
    
    # Insurance and billing
    insurance_type: Optional[InsuranceType] = None
    insurance_coverage: Optional[float] = None  # Percentage (0-100)
    
    # Dates
    service_date: Optional[datetime] = None
    admission_date: Optional[datetime] = None
    discharge_date: Optional[datetime] = None
    
    # Additional data
    raw_text: str = ""
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    
    def __post_init__(self):
        """Validate and normalize data after initialization."""
        if self.insurance_coverage is not None:
            self.insurance_coverage = max(0, min(100, self.insurance_coverage))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'patient_id': self.patient_id,
            'patient_name': self.patient_name,
            'age': self.age,
            'procedure_codes': self.procedure_codes,
            'diagnosis_codes': self.diagnosis_codes,
            'procedure_type': self.procedure_type.value if self.procedure_type else None,
            'insurance_type': self.insurance_type.value if self.insurance_type else None,
            'insurance_coverage': self.insurance_coverage,
            'service_date': self.service_date.isoformat() if self.service_date else None,
            'admission_date': self.admission_date.isoformat() if self.admission_date else None,
            'discharge_date': self.discharge_date.isoformat() if self.discharge_date else None,
            'raw_text': self.raw_text,
            'extracted_fields': self.extracted_fields,
            'confidence_score': self.confidence_score
        }


@dataclass
class PricingResult:
    """Container for pricing calculation results."""
    
    # Basic pricing
    base_price: float
    insurance_adjustment: float = 0.0
    final_price: float = 0.0
    
    # Detailed breakdown
    procedure_costs: Dict[str, float] = field(default_factory=dict)
    adjustment_factors: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    calculation_date: datetime = field(default_factory=datetime.now)
    pricing_model_version: str = "1.0"
    confidence_level: float = 0.0
    
    # Additional information
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate final price if not provided."""
        if self.final_price == 0.0:
            self.final_price = max(0, self.base_price + self.insurance_adjustment)
    
    def add_note(self, note: str):
        """Add a note to the pricing result."""
        self.notes.append(note)
    
    def add_warning(self, warning: str):
        """Add a warning to the pricing result."""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'base_price': self.base_price,
            'insurance_adjustment': self.insurance_adjustment,
            'final_price': self.final_price,
            'procedure_costs': self.procedure_costs,
            'adjustment_factors': self.adjustment_factors,
            'calculation_date': self.calculation_date.isoformat(),
            'pricing_model_version': self.pricing_model_version,
            'confidence_level': self.confidence_level,
            'notes': self.notes,
            'warnings': self.warnings
        }