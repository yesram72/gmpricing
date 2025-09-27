#!/usr/bin/env python3
"""
GM Pricing Application Demo

This script demonstrates the complete functionality of the medical pricing application.
"""

import json
from pathlib import Path
import subprocess
import sys

def run_command(cmd):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"Command failed with exit code: {result.returncode}")
        return False
    
    return True

def main():
    """Run the demo."""
    print("GM Pricing Application Demo")
    print("=" * 40)
    
    # 1. Show application info
    print("\n1. Application Information:")
    run_command([sys.executable, "main.py", "info"])
    
    # 2. Create sample data
    print("\n2. Creating Sample Data:")
    run_command([sys.executable, "main.py", "create-sample"])
    
    # 3. Process documents to extract medical data
    print("\n3. Processing Medical Documents:")
    if run_command([sys.executable, "main.py", "process", "sample_data/sample_medical_report.txt"]):
        
        # Show the extracted data
        output_files = list(Path("output").glob("gmpricing_results_*.json"))
        if output_files:
            latest_file = max(output_files, key=lambda f: f.stat().st_mtime)
            print(f"\nExtracted Data from {latest_file.name}:")
            with open(latest_file, 'r') as f:
                data = json.load(f)
                medical_data = data[0]['medical_data']
                print(f"  Patient: {medical_data.get('patient_name', 'N/A')} (ID: {medical_data.get('patient_id', 'N/A')})")
                print(f"  Age: {medical_data.get('age', 'N/A')}")
                print(f"  Procedure Codes: {medical_data.get('procedure_codes', [])}")
                print(f"  Diagnosis Codes: {medical_data.get('diagnosis_codes', [])}")
                print(f"  Insurance: {medical_data.get('insurance_type', 'N/A')} ({medical_data.get('insurance_coverage', 0)}% coverage)")
                print(f"  Confidence: {medical_data.get('confidence_score', 0):.1f}%")
    
    # 4. Calculate pricing
    print("\n4. Calculating Medical Pricing:")
    if run_command([sys.executable, "main.py", "price", "sample_data/sample_medical_report.txt"]):
        
        # Show the pricing results
        pricing_files = list(Path("output").glob("pricing_results_*.csv"))
        if pricing_files:
            latest_file = max(pricing_files, key=lambda f: f.stat().st_mtime)
            print(f"\nPricing Results from {latest_file.name}:")
            with open(latest_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    header = lines[0].strip().split(',')
                    data = lines[1].strip().split(',')
                    print(f"  Base Price: {data[0]}")
                    print(f"  Insurance Adjustment: {data[1]}")
                    print(f"  Final Price (Patient Pays): {data[2]}")
                    print(f"  Confidence Level: {data[4]}")
    
    # 5. Run full analysis
    print("\n5. Running Complete Analysis Pipeline:")
    run_command([sys.executable, "main.py", "analyze", "sample_data/"])
    
    # 6. Show file outputs
    print("\n6. Generated Output Files:")
    output_dir = Path("output")
    if output_dir.exists():
        files = list(output_dir.glob("*"))
        for file in sorted(files, key=lambda f: f.stat().st_mtime):
            size = file.stat().st_size
            print(f"  {file.name} ({size} bytes)")
    
    print("\n" + "="*60)
    print("Demo completed successfully!")
    print("="*60)
    
    print("\nSUMMARY:")
    print("✅ Medical document processing: Extracts patient info, codes, insurance")
    print("✅ Pricing calculation: Applies pricing rules and insurance adjustments") 
    print("✅ Multiple output formats: JSON for data, CSV for pricing")
    print("✅ Comprehensive validation: Data quality checks and confidence scoring")
    print("✅ Command-line interface: Easy to use with multiple commands")
    
    print("\nNEXT STEPS:")
    print("- Install PDF libraries (PyPDF2, pdfplumber) for PDF support")
    print("- Install OCR libraries (pytesseract, Pillow, pdf2image) for scanned documents")
    print("- Customize pricing rules in config.json")
    print("- Add custom medical procedure codes and pricing")
    print("- Process your own medical documents")

if __name__ == "__main__":
    main()