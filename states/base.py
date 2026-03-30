"""Abstract base class for state scrapers."""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Dict, Any


class StateScraper(ABC):
    """Base class for state-specific business filing scrapers."""

    @property
    @abstractmethod
    def state_code(self) -> str:
        """Two-letter state code (e.g., 'FL', 'NY')."""
        ...

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier for the CSV (e.g., 'sunbiz_sftp')."""
        ...

    @abstractmethod
    def fetch(self, target_date: date) -> List[Dict[str, Any]]:
        """Fetch new business filings for the given date.

        Returns a list of dicts, each representing one business entity
        with raw fields from the state's data source.
        """
        ...
