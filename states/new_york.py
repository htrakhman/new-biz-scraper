"""New York business filings scraper — Socrata Open Data API."""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any

import requests

from config import NY_FILINGS_URL, NY_ADDRESS_URL, NY_API_LIMIT
from states.base import StateScraper

logger = logging.getLogger(__name__)


class NewYorkScraper(StateScraper):
    state_code = "NY"
    source_name = "data_ny_gov"

    def fetch(self, target_date: date) -> List[Dict[str, Any]]:
        # Try target date first, walk back up to 5 business days if no results
        current = target_date
        for attempt in range(6):
            filings = self._fetch_filings(current)
            if filings:
                if current != target_date:
                    logger.warning(
                        f"No NY filings for {target_date}, using {current} instead"
                    )
                logger.info(f"Fetched {len(filings)} NY filings for {current}")
                return filings
            logger.debug(f"No NY filings for {current}")
            current -= timedelta(days=1)
            while current.weekday() >= 5:
                current -= timedelta(days=1)

        logger.warning(f"No NY filings found within 5 business days of {target_date}")
        return []

    def _fetch_filings(self, target_date: date) -> List[Dict[str, Any]]:
        """Fetch filings for the target date from the Socrata API."""
        next_date = target_date + timedelta(days=1)
        where_clause = (
            f"filing_date >= '{target_date.isoformat()}T00:00:00' "
            f"AND filing_date < '{next_date.isoformat()}T00:00:00'"
        )
        params = {
            "$where": where_clause,
            "$limit": NY_API_LIMIT,
            "$order": "filing_date DESC",
        }

        try:
            resp = requests.get(NY_FILINGS_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"NY API returned {len(data)} filings for {target_date}")
            return data
        except requests.RequestException as e:
            logger.error(f"NY filings API request failed: {e}")
            return []
