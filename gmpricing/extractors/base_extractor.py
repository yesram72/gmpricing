"""
Base extractor class providing common interface for all data extractors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
from pathlib import Path


class BaseExtractor(ABC):
    """Abstract base class for all data extractors."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the extractor with configuration.
        
        Args:
            config: Configuration dictionary for the extractor
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract data from the given file.
        
        Args:
            file_path: Path to the file to extract data from
            
        Returns:
            Dictionary containing extracted data
        """
        pass
    
    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """
        Check if this extractor can handle the given file type.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if this extractor can handle the file
        """
        pass
    
    def validate_file(self, file_path: Path) -> bool:
        """
        Validate that the file exists and is accessible.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            True if file is valid
        """
        if not file_path.exists():
            self.logger.error(f"File does not exist: {file_path}")
            return False
        
        if not file_path.is_file():
            self.logger.error(f"Path is not a file: {file_path}")
            return False
        
        if file_path.stat().st_size == 0:
            self.logger.warning(f"File is empty: {file_path}")
            return False
        
        return True
    
    def get_supported_extensions(self) -> List[str]:
        """
        Get list of file extensions supported by this extractor.
        
        Returns:
            List of supported file extensions (including the dot)
        """
        return []