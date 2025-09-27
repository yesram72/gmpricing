"""
Pricing calculator for medical procedures and services.
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from .models import MedicalData, PricingResult, ProcedureType, InsuranceType


class PricingCalculator:
    """Calculate medical pricing based on extracted data."""
    
    # Base pricing table for common procedures (CPT codes)
    BASE_PRICES = {
        # Consultation codes
        '99201': 150.00,  # New patient visit - straightforward
        '99202': 200.00,  # New patient visit - low complexity
        '99203': 250.00,  # New patient visit - moderate complexity
        '99204': 350.00,  # New patient visit - moderate to high complexity
        '99205': 450.00,  # New patient visit - high complexity
        '99211': 75.00,   # Established patient visit - minimal
        '99212': 125.00,  # Established patient visit - straightforward
        '99213': 175.00,  # Established patient visit - low complexity
        '99214': 225.00,  # Established patient visit - moderate complexity
        '99215': 275.00,  # Established patient visit - high complexity
        
        # Emergency department visits
        '99281': 150.00,  # ED visit - straightforward
        '99282': 250.00,  # ED visit - low complexity
        '99283': 350.00,  # ED visit - moderate complexity
        '99284': 500.00,  # ED visit - moderate to high complexity
        '99285': 750.00,  # ED visit - high complexity
        
        # Diagnostic procedures
        '70450': 400.00,  # CT head without contrast
        '70460': 600.00,  # CT head with contrast
        '71020': 200.00,  # Chest X-ray
        '73721': 500.00,  # MRI knee without contrast
        '76700': 300.00,  # Abdominal ultrasound
        
        # Common surgical procedures
        '11401': 350.00,  # Excision benign lesion
        '27447': 15000.00, # Total knee replacement
        '47562': 8000.00,  # Laparoscopic cholecystectomy
        '44970': 6000.00,  # Laparoscopic appendectomy
        '29881': 4000.00,  # Knee arthroscopy
    }
    
    # Procedure type multipliers
    PROCEDURE_TYPE_MULTIPLIERS = {
        ProcedureType.CONSULTATION: 1.0,
        ProcedureType.DIAGNOSTIC: 1.2,
        ProcedureType.TREATMENT: 1.5,
        ProcedureType.SURGERY: 2.0,
        ProcedureType.EMERGENCY: 1.8,
    }
    
    # Insurance coverage adjustments (percentage of base price)
    INSURANCE_ADJUSTMENTS = {
        InsuranceType.PRIVATE: 0.85,    # Private insurance typically covers 85%
        InsuranceType.PUBLIC: 0.70,     # Medicare/Medicaid covers 70%
        InsuranceType.SELF_PAY: 1.0,    # Self-pay gets discount sometimes
        InsuranceType.MIXED: 0.80,      # Mixed coverage
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize pricing calculator.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load custom pricing if provided
        custom_prices = self.config.get('custom_prices', {})
        self.prices = {**self.BASE_PRICES, **custom_prices}
        
        # Load custom multipliers if provided
        custom_multipliers = self.config.get('procedure_multipliers', {})
        self.procedure_multipliers = {**self.PROCEDURE_TYPE_MULTIPLIERS, **custom_multipliers}
        
        # Default pricing for unknown procedures
        self.default_price = self.config.get('default_price', 200.00)
        
        # Self-pay discount
        self.self_pay_discount = self.config.get('self_pay_discount', 0.20)  # 20% discount
    
    def calculate_pricing(self, medical_data: MedicalData) -> PricingResult:
        """
        Calculate pricing based on medical data.
        
        Args:
            medical_data: Extracted medical data
            
        Returns:
            PricingResult with calculated pricing
        """
        try:
            # Calculate base price from procedures
            base_price, procedure_costs = self._calculate_base_price(medical_data)
            
            # Apply procedure type multiplier
            procedure_multiplier = self._get_procedure_multiplier(medical_data.procedure_type)
            base_price *= procedure_multiplier
            
            # Calculate insurance adjustment
            insurance_adjustment = self._calculate_insurance_adjustment(
                base_price, medical_data.insurance_type, medical_data.insurance_coverage
            )
            
            # Create result
            result = PricingResult(
                base_price=base_price,
                insurance_adjustment=insurance_adjustment,
                procedure_costs=procedure_costs,
                adjustment_factors={
                    'procedure_type_multiplier': procedure_multiplier,
                    'insurance_type': medical_data.insurance_type.value if medical_data.insurance_type else 'unknown',
                    'insurance_coverage': medical_data.insurance_coverage or 0.0
                },
                confidence_level=self._calculate_pricing_confidence(medical_data)
            )
            
            # Add notes and warnings
            self._add_pricing_notes(result, medical_data)
            
            self.logger.info(f"Calculated pricing: Base ${base_price:.2f}, "
                           f"Adjustment ${insurance_adjustment:.2f}, "
                           f"Final ${result.final_price:.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating pricing: {str(e)}")
            # Return default pricing with error
            result = PricingResult(
                base_price=self.default_price,
                confidence_level=0.0
            )
            result.add_warning(f"Error in pricing calculation: {str(e)}")
            return result
    
    def _calculate_base_price(self, medical_data: MedicalData) -> tuple[float, Dict[str, float]]:
        """
        Calculate base price from procedure codes.
        
        Args:
            medical_data: Medical data with procedure codes
            
        Returns:
            Tuple of (total_base_price, procedure_costs_dict)
        """
        total_price = 0.0
        procedure_costs = {}
        
        if not medical_data.procedure_codes:
            # No specific procedures found, use default
            total_price = self.default_price
            procedure_costs['default'] = self.default_price
            self.logger.warning("No procedure codes found, using default pricing")
        else:
            for code in medical_data.procedure_codes:
                if code in self.prices:
                    price = self.prices[code]
                    total_price += price
                    procedure_costs[code] = price
                    self.logger.debug(f"Found price for {code}: ${price:.2f}")
                else:
                    # Unknown procedure code, use default
                    price = self.default_price
                    total_price += price
                    procedure_costs[code] = price
                    self.logger.warning(f"Unknown procedure code {code}, using default price")
        
        return total_price, procedure_costs
    
    def _get_procedure_multiplier(self, procedure_type: Optional[ProcedureType]) -> float:
        """
        Get multiplier based on procedure type.
        
        Args:
            procedure_type: Type of medical procedure
            
        Returns:
            Multiplier value
        """
        if procedure_type and procedure_type in self.procedure_multipliers:
            return self.procedure_multipliers[procedure_type]
        return 1.0  # Default multiplier
    
    def _calculate_insurance_adjustment(
        self, 
        base_price: float, 
        insurance_type: Optional[InsuranceType], 
        coverage_percentage: Optional[float]
    ) -> float:
        """
        Calculate insurance adjustment to base price.
        
        Args:
            base_price: Base price before insurance
            insurance_type: Type of insurance
            coverage_percentage: Insurance coverage percentage
            
        Returns:
            Adjustment amount (negative for discounts)
        """
        if not insurance_type:
            return 0.0  # No insurance information
        
        if insurance_type == InsuranceType.SELF_PAY:
            # Apply self-pay discount
            discount = base_price * self.self_pay_discount
            return -discount
        
        # Use specific coverage percentage if provided
        if coverage_percentage is not None:
            coverage_ratio = coverage_percentage / 100.0
        else:
            # Use default coverage for insurance type
            coverage_ratio = self.INSURANCE_ADJUSTMENTS.get(insurance_type, 0.8)
        
        # Calculate patient responsibility (what they pay)
        patient_pays = base_price * (1 - coverage_ratio)
        
        # Adjustment is the difference from base price
        return patient_pays - base_price
    
    def _calculate_pricing_confidence(self, medical_data: MedicalData) -> float:
        """
        Calculate confidence in pricing calculation.
        
        Args:
            medical_data: Medical data used for pricing
            
        Returns:
            Confidence score (0-100)
        """
        confidence = 0.0
        
        # Base confidence from data extraction
        confidence += medical_data.confidence_score * 0.3
        
        # Confidence from procedure codes
        if medical_data.procedure_codes:
            known_codes = sum(1 for code in medical_data.procedure_codes if code in self.prices)
            code_confidence = (known_codes / len(medical_data.procedure_codes)) * 40
            confidence += code_confidence
        else:
            confidence += 10  # Some confidence even without codes
        
        # Confidence from insurance information
        if medical_data.insurance_type:
            confidence += 15
            if medical_data.insurance_coverage is not None:
                confidence += 10
        
        # Confidence from procedure type
        if medical_data.procedure_type:
            confidence += 10
        
        # Confidence from patient information
        if medical_data.patient_id and medical_data.service_date:
            confidence += 5
        
        return min(confidence, 100.0)
    
    def _add_pricing_notes(self, result: PricingResult, medical_data: MedicalData):
        """
        Add notes and warnings to pricing result.
        
        Args:
            result: Pricing result to add notes to
            medical_data: Medical data used for calculation
        """
        # Add notes about procedure codes
        if medical_data.procedure_codes:
            known_codes = [code for code in medical_data.procedure_codes if code in self.prices]
            unknown_codes = [code for code in medical_data.procedure_codes if code not in self.prices]
            
            if known_codes:
                result.add_note(f"Recognized procedure codes: {', '.join(known_codes)}")
            
            if unknown_codes:
                result.add_warning(f"Unknown procedure codes (using default pricing): {', '.join(unknown_codes)}")
        else:
            result.add_warning("No procedure codes found - using default pricing")
        
        # Add notes about insurance
        if medical_data.insurance_type:
            result.add_note(f"Insurance type: {medical_data.insurance_type.value}")
            if medical_data.insurance_coverage:
                result.add_note(f"Insurance coverage: {medical_data.insurance_coverage}%")
        else:
            result.add_warning("No insurance information found")
        
        # Add notes about confidence
        if result.confidence_level < 50:
            result.add_warning("Low confidence in pricing calculation - verify manually")
        elif result.confidence_level < 70:
            result.add_note("Moderate confidence in pricing calculation")
        else:
            result.add_note("High confidence in pricing calculation")
    
    def get_procedure_info(self, procedure_code: str) -> Dict[str, Any]:
        """
        Get information about a specific procedure code.
        
        Args:
            procedure_code: CPT procedure code
            
        Returns:
            Dictionary with procedure information
        """
        if procedure_code in self.prices:
            return {
                'code': procedure_code,
                'base_price': self.prices[procedure_code],
                'known': True
            }
        else:
            return {
                'code': procedure_code,
                'base_price': self.default_price,
                'known': False
            }
    
    def add_custom_pricing(self, procedure_code: str, price: float):
        """
        Add or update custom pricing for a procedure code.
        
        Args:
            procedure_code: CPT procedure code
            price: Price for the procedure
        """
        self.prices[procedure_code] = price
        self.logger.info(f"Added custom pricing: {procedure_code} = ${price:.2f}")
    
    def get_pricing_summary(self) -> Dict[str, Any]:
        """
        Get summary of available pricing information.
        
        Returns:
            Dictionary with pricing summary
        """
        return {
            'total_procedures': len(self.prices),
            'default_price': self.default_price,
            'procedure_types': list(self.procedure_multipliers.keys()),
            'insurance_types': list(self.INSURANCE_ADJUSTMENTS.keys()),
            'self_pay_discount': self.self_pay_discount
        }