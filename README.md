# GM Pricing - Medical Pricing Algorithm Application

A Python application that reads data from unstructured files (PDFs and scanned PDFs as images), extracts medical information, applies calculations, and produces pricing estimates for medical services.

## Overview

GM Pricing is designed to process medical documents and automatically extract key information such as:
- Patient demographics
- Procedure codes (CPT)
- Diagnosis codes (ICD-10)
- Insurance information
- Service dates

The application then calculates pricing based on extracted data using configurable pricing rules and insurance adjustments.

## Features

- **Multi-format Support**: Processes both text-based PDFs and scanned documents using OCR
- **Intelligent Extraction**: Uses pattern matching and medical code recognition
- **Flexible Pricing**: Configurable pricing tables and adjustment factors
- **Insurance Processing**: Handles different insurance types and coverage calculations
- **Validation**: Comprehensive data validation and quality assessment
- **Batch Processing**: Process individual files or entire directories
- **Multiple Output Formats**: JSON and CSV export options
- **Comprehensive Logging**: Detailed logging with configurable levels

## Installation

### Prerequisites

- Python 3.8 or higher
- Tesseract OCR (for image processing)

### Install Tesseract OCR

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### Install GM Pricing

1. Clone the repository:
```bash
git clone https://github.com/yesram72/gmpricing.git
cd gmpricing
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install the application:
```bash
pip install -e .
```

## Quick Start

### 1. Create Sample Data
```bash
python main.py create-sample
```

### 2. Process a File
```bash
python main.py process sample_data/sample_medical_report.txt
```

### 3. Calculate Pricing
```bash
python main.py price sample_data/sample_medical_report.txt
```

### 4. Run Full Analysis
```bash
python main.py analyze sample_data/
```

## Usage

### Command Line Interface

The application provides several commands:

#### Process Documents
Extract medical data from documents:
```bash
python main.py process <input_path> [options]
```

Options:
- `--output, -o`: Output file path
- `--format`: Output format (json, csv)
- `--verbose, -v`: Enable verbose logging

#### Calculate Pricing
Calculate pricing for medical data:
```bash
python main.py price <input_path> [options]
```

#### Full Analysis
Run complete analysis pipeline:
```bash
python main.py analyze <input_path> [options]
```

#### Application Info
Display application information:
```bash
python main.py info
```

### Configuration

The application can be configured using a JSON configuration file:

```bash
python main.py --config config.json process documents/
```

Example configuration:
```json
{
  "file_handler": {
    "output_dir": "output",
    "pdf_extractor": {
      "use_pdfplumber": true
    },
    "ocr_extractor": {
      "dpi": 300,
      "language": "eng"
    }
  },
  "pricing": {
    "default_price": 200.0,
    "self_pay_discount": 0.20
  },
  "validator": {
    "min_confidence": 30.0,
    "require_procedure_codes": true
  }
}
```

## Supported File Types

- **PDF**: `.pdf` (both text-based and scanned)
- **Images**: `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.gif`

## Medical Code Support

### Procedure Codes (CPT)
The application recognizes standard CPT codes and includes pricing for common procedures:
- Office visits (99201-99215)
- Emergency visits (99281-99285)
- Diagnostic procedures (70450, 71020, etc.)
- Surgical procedures (27447, 47562, etc.)

### Diagnosis Codes (ICD-10)
Supports standard ICD-10 format: Letter + 2 digits + optional decimal + additional digits

### Insurance Types
- Private Insurance
- Public Insurance (Medicare/Medicaid)
- Self-Pay
- Mixed Coverage

## Output Examples

### JSON Output (Processing)
```json
{
  "medical_data": {
    "patient_id": "MRN123456",
    "patient_name": "John Smith",
    "age": 45,
    "procedure_codes": ["99213"],
    "diagnosis_codes": ["I10"],
    "insurance_type": "private",
    "confidence_score": 87.5
  },
  "extraction_method": "pdfplumber",
  "processed_at": "2024-03-15T10:30:00"
}
```

### CSV Output (Pricing)
```csv
Base Price,Insurance Adjustment,Final Price,Procedure Costs,Confidence Level
$175.00,$-26.25,$148.75,99213: $175.00,85.0%
```

## Architecture

### Core Components

1. **Extractors**: Handle document processing and data extraction
   - `PDFExtractor`: For text-based PDFs
   - `OCRExtractor`: For scanned documents and images

2. **Pricing Engine**: Calculate costs based on extracted data
   - `PricingCalculator`: Core pricing logic
   - `MedicalData`: Data models for medical information

3. **Utilities**: Support functionality
   - `FileHandler`: File I/O operations
   - `DataValidator`: Data validation and quality checks
   - `Logger`: Comprehensive logging system

### Processing Pipeline

1. **File Input**: Accept PDF or image files
2. **Data Extraction**: Extract text using appropriate method
3. **Medical Data Parsing**: Identify medical codes, patient info, etc.
4. **Validation**: Validate extracted data quality
5. **Pricing Calculation**: Apply pricing rules and adjustments
6. **Output Generation**: Export results in requested format

## Error Handling

The application includes comprehensive error handling:
- File validation (existence, format, accessibility)
- Data validation (format, completeness, reasonableness)
- Processing errors (OCR failures, parsing issues)
- Pricing validation (negative values, unreasonable amounts)

## Logging

Detailed logging is available at multiple levels:
- Console output for user feedback
- File logging for detailed debugging
- Separate error logs for troubleshooting
- Configurable log rotation and retention

## Performance Considerations

- **Batch Processing**: Efficiently process multiple files
- **Memory Management**: Handles large documents appropriately
- **OCR Optimization**: Configurable DPI and preprocessing
- **Caching**: Avoids redundant processing where possible

## Development

### Project Structure
```
gmpricing/
├── gmpricing/           # Main package
│   ├── extractors/      # Document processing modules
│   ├── pricing/         # Pricing calculation modules
│   └── utils/           # Utility modules
├── main.py              # CLI entry point
├── requirements.txt     # Dependencies
├── setup.py            # Installation script
└── config.json         # Configuration file
```

### Running Tests
```bash
python -m pytest tests/
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## Troubleshooting

### Common Issues

**OCR not working:**
- Ensure Tesseract is installed and in PATH
- Check image quality and resolution
- Verify supported file formats

**Low confidence scores:**
- Check document quality
- Verify medical codes are present
- Review extraction patterns

**Pricing errors:**
- Validate procedure codes
- Check insurance information
- Review pricing configuration

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the logs for detailed error information
