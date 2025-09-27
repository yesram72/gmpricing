"""
Logging configuration for the medical pricing application.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
import sys


def setup_logger(
    name: str = 'gmpricing',
    level: str = 'INFO',
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Log file name (if None, uses name.log)
        log_dir: Log directory (if None, uses 'logs')
        config: Additional configuration options
        
    Returns:
        Configured logger instance
    """
    config = config or {}
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Set level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if requested)
    if config.get('log_to_file', True):
        # Set up log directory
        if log_dir is None:
            log_dir = 'logs'
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # Set up log file name
        if log_file is None:
            log_file = f'{name}.log'
        
        log_file_path = log_path / log_file
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=config.get('max_log_size', 10 * 1024 * 1024),  # 10MB
            backupCount=config.get('backup_count', 5)
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    
    # Error file handler (separate file for errors)
    if config.get('separate_error_log', True):
        if log_dir is None:
            log_dir = 'logs'
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        error_file_path = log_path / f'{name}_errors.log'
        
        error_handler = logging.handlers.RotatingFileHandler(
            error_file_path,
            maxBytes=config.get('max_log_size', 10 * 1024 * 1024),  # 10MB
            backupCount=config.get('backup_count', 5)
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
    
    logger.info(f"Logger '{name}' initialized with level {level}")
    
    return logger


def configure_library_loggers(level: str = 'WARNING'):
    """
    Configure logging levels for third-party libraries.
    
    Args:
        level: Logging level for libraries
    """
    # Reduce noise from third-party libraries
    library_loggers = [
        'PIL',
        'pytesseract',
        'pdfplumber',
        'PyPDF2',
        'pdf2image'
    ]
    
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    
    for lib_name in library_loggers:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)