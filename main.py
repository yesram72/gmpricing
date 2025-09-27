#!/usr/bin/env python3
"""
GM Pricing - Medical Pricing Algorithm Application

Main entry point for processing medical documents and calculating pricing.
"""

import click
import json
from pathlib import Path
from typing import Optional, Dict, Any
import sys

from gmpricing.utils.logger import setup_logger, configure_library_loggers
from gmpricing.utils.file_handler import FileHandler
from gmpricing.utils.validator import DataValidator
from gmpricing.pricing.calculator import PricingCalculator
from gmpricing.pricing.models import MedicalData


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--log-file', help='Log file path')
@click.option('--config', help='Configuration file path')
@click.pass_context
def cli(ctx, verbose, log_file, config):
    """GM Pricing - Medical document processing and pricing calculator."""
    # Ensure context exists
    ctx.ensure_object(dict)
    
    # Set up logging
    log_level = 'DEBUG' if verbose else 'INFO'
    logger = setup_logger('gmpricing', level=log_level, log_file=log_file)
    configure_library_loggers()
    
    # Load configuration
    app_config = {}
    if config:
        config_path = Path(config)
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    app_config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Error loading configuration: {e}")
                sys.exit(1)
        else:
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
    
    # Store in context
    ctx.obj['config'] = app_config
    ctx.obj['logger'] = logger


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv']), 
              default='json', help='Output format')
@click.pass_context  
def process(ctx, input_path, output, output_format):
    """Process medical documents and extract data."""
    logger = ctx.obj['logger']
    config = ctx.obj['config']
    
    logger.info(f"Processing: {input_path}")
    
    # Initialize components
    file_handler = FileHandler(config.get('file_handler', {}))
    validator = DataValidator(config.get('validator', {}))
    
    input_path = Path(input_path)
    
    try:
        # Process file or directory
        if input_path.is_file():
            results = [file_handler.process_file(input_path)]
        elif input_path.is_dir():
            results = file_handler.process_directory(input_path)
        else:
            logger.error(f"Invalid input path: {input_path}")
            sys.exit(1)
        
        # Validate results
        validation_report = validator.generate_validation_report(results)
        
        logger.info(f"Processed {validation_report['total_files']} files")
        logger.info(f"Valid: {validation_report['valid_files']}, "
                   f"Invalid: {validation_report['invalid_files']}")
        
        if validation_report['invalid_files'] > 0:
            logger.warning("Some files had validation errors:")
            for error in validation_report['errors'][:5]:  # Show first 5 errors
                logger.warning(f"  - {error}")
        
        # Save results
        if output_format == 'json':
            output_path = file_handler.save_results(results, output)
            logger.info(f"Results saved to: {output_path}")
        else:
            logger.error("CSV format not implemented for extraction results")
            sys.exit(1)
        
        # Display summary
        click.echo(f"\nProcessing Summary:")
        click.echo(f"  Total files: {validation_report['total_files']}")
        click.echo(f"  Valid files: {validation_report['valid_files']}")
        click.echo(f"  Invalid files: {validation_report['invalid_files']}")
        click.echo(f"  Success rate: {validation_report['summary']['success_rate']:.1f}%")
        
        if 'avg_confidence' in validation_report['summary']:
            click.echo(f"  Average confidence: {validation_report['summary']['avg_confidence']:.1f}%")
        
    except Exception as e:
        logger.error(f"Error processing files: {e}")
        sys.exit(1)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.option('--format', 'output_format', type=click.Choice(['json', 'csv']), 
              default='csv', help='Output format')
@click.pass_context
def price(ctx, input_path, output, output_format):
    """Calculate pricing for processed medical data."""
    logger = ctx.obj['logger']
    config = ctx.obj['config']
    
    logger.info(f"Calculating pricing for: {input_path}")
    
    # Initialize components
    file_handler = FileHandler(config.get('file_handler', {}))
    pricing_calculator = PricingCalculator(config.get('pricing', {}))
    validator = DataValidator(config.get('validator', {}))
    
    input_path = Path(input_path)
    
    try:
        # Process files to extract medical data
        if input_path.is_file():
            results = [file_handler.process_file(input_path)]
        elif input_path.is_dir():
            results = file_handler.process_directory(input_path)
        else:
            logger.error(f"Invalid input path: {input_path}")
            sys.exit(1)
        
        # Calculate pricing for each result
        pricing_results = []
        total_files = len(results)
        successful_pricing = 0
        
        for i, result in enumerate(results, 1):
            file_name = result.get('file_name', f'File_{i}')
            click.echo(f"Processing {i}/{total_files}: {file_name}")
            
            if 'error' in result:
                logger.warning(f"Skipping {file_name} due to extraction error: {result['error']}")
                continue
            
            if 'medical_data' not in result:
                logger.warning(f"Skipping {file_name} - no medical data extracted")
                continue
            
            # Get medical data
            medical_data = result['medical_data']
            if isinstance(medical_data, dict):
                try:
                    medical_data = MedicalData(**medical_data)
                except Exception as e:
                    logger.error(f"Error creating MedicalData for {file_name}: {e}")
                    continue
            
            # Validate medical data
            is_valid, errors = validator.validate_medical_data(medical_data)
            if not is_valid:
                logger.warning(f"Validation errors for {file_name}: {'; '.join(errors)}")
                # Continue with pricing despite validation warnings
            
            # Calculate pricing
            try:
                pricing_result = pricing_calculator.calculate_pricing(medical_data)
                pricing_results.append(pricing_result)
                successful_pricing += 1
                
                click.echo(f"  Base: ${pricing_result.base_price:.2f}, "
                          f"Final: ${pricing_result.final_price:.2f}, "
                          f"Confidence: {pricing_result.confidence_level:.1f}%")
                
            except Exception as e:
                logger.error(f"Error calculating pricing for {file_name}: {e}")
        
        if not pricing_results:
            logger.error("No pricing calculations were successful")
            sys.exit(1)
        
        # Save pricing results
        if output_format == 'csv':
            output_path = file_handler.save_pricing_results(pricing_results, output)
        else:
            # Convert to JSON format
            json_results = [result.to_dict() for result in pricing_results]
            output_path = file_handler.save_results(json_results, output)
        
        logger.info(f"Pricing results saved to: {output_path}")
        
        # Display summary
        total_base_price = sum(r.base_price for r in pricing_results)
        total_final_price = sum(r.final_price for r in pricing_results)
        avg_confidence = sum(r.confidence_level for r in pricing_results) / len(pricing_results)
        
        click.echo(f"\nPricing Summary:")
        click.echo(f"  Processed files: {successful_pricing}/{total_files}")
        click.echo(f"  Total base price: ${total_base_price:.2f}")
        click.echo(f"  Total final price: ${total_final_price:.2f}")
        click.echo(f"  Average confidence: {avg_confidence:.1f}%")
        click.echo(f"  Results saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error calculating pricing: {e}")
        sys.exit(1)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file path')
@click.pass_context
def analyze(ctx, input_path, output):
    """Analyze and process medical documents with full pipeline."""
    logger = ctx.obj['logger']
    config = ctx.obj['config']
    
    logger.info(f"Running full analysis pipeline for: {input_path}")
    
    # Initialize components
    file_handler = FileHandler(config.get('file_handler', {}))
    pricing_calculator = PricingCalculator(config.get('pricing', {}))
    validator = DataValidator(config.get('validator', {}))
    
    input_path = Path(input_path)
    
    try:
        # Process files
        if input_path.is_file():
            results = [file_handler.process_file(input_path)]
        elif input_path.is_dir():
            results = file_handler.process_directory(input_path)
        else:
            logger.error(f"Invalid input path: {input_path}")
            sys.exit(1)
        
        # Generate validation report
        validation_report = validator.generate_validation_report(results)
        
        # Calculate pricing for valid results
        pricing_results = []
        for result in results:
            if 'medical_data' in result and not result.get('error'):
                medical_data = result['medical_data']
                if isinstance(medical_data, dict):
                    medical_data = MedicalData(**medical_data)
                
                pricing_result = pricing_calculator.calculate_pricing(medical_data)
                pricing_results.append(pricing_result)
        
        # Create comprehensive analysis
        analysis = {
            'extraction_results': results,
            'validation_report': validation_report,
            'pricing_results': [r.to_dict() for r in pricing_results],
            'analysis_summary': {
                'total_files': len(results),
                'successful_extractions': validation_report['valid_files'],
                'successful_pricing_calculations': len(pricing_results),
                'total_estimated_cost': sum(r.final_price for r in pricing_results),
                'analysis_timestamp': ctx.obj.get('timestamp', 'unknown')
            }
        }
        
        # Save comprehensive analysis
        output_path = file_handler.save_results(analysis, output)
        logger.info(f"Analysis saved to: {output_path}")
        
        # Display results
        click.echo(f"\nComprehensive Analysis Summary:")
        click.echo(f"  Files processed: {analysis['analysis_summary']['total_files']}")
        click.echo(f"  Successful extractions: {analysis['analysis_summary']['successful_extractions']}")
        click.echo(f"  Successful pricing: {analysis['analysis_summary']['successful_pricing_calculations']}")
        click.echo(f"  Total estimated cost: ${analysis['analysis_summary']['total_estimated_cost']:.2f}")
        click.echo(f"  Results saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        sys.exit(1)


@cli.command()
@click.option('--output-dir', default='sample_data', help='Output directory for sample files')
@click.pass_context
def create_sample(ctx, output_dir):
    """Create sample medical data files for testing."""
    logger = ctx.obj['logger']
    config = ctx.obj['config']
    
    file_handler = FileHandler(config.get('file_handler', {}))
    
    try:
        sample_dir = file_handler.create_sample_data(Path(output_dir))
        click.echo(f"Sample data created in: {sample_dir}")
        
        # List created files
        sample_files = list(sample_dir.glob("*"))
        if sample_files:
            click.echo("Created files:")
            for file_path in sample_files:
                click.echo(f"  - {file_path.name}")
        
    except Exception as e:
        logger.error(f"Error creating sample data: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def info(ctx):
    """Display application information and configuration."""
    logger = ctx.obj['logger']
    config = ctx.obj['config']
    
    click.echo("GM Pricing - Medical Pricing Algorithm Application")
    click.echo("=" * 50)
    
    # Show version info
    try:
        from gmpricing import __version__
        click.echo(f"Version: {__version__}")
    except ImportError:
        click.echo("Version: Development")
    
    # Show supported file types
    file_handler = FileHandler()
    supported_types = file_handler.get_supported_file_types()
    click.echo(f"Supported file types: {', '.join(supported_types)}")
    
    # Show pricing information
    pricing_calculator = PricingCalculator()
    pricing_summary = pricing_calculator.get_pricing_summary()
    click.echo(f"Available procedure codes: {pricing_summary['total_procedures']}")
    click.echo(f"Default procedure price: ${pricing_summary['default_price']:.2f}")
    
    # Show configuration
    if config:
        click.echo("\nActive Configuration:")
        click.echo(json.dumps(config, indent=2))
    
    click.echo("\nFor more information, use --help with any command.")


if __name__ == '__main__':
    cli()