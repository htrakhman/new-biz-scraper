"""Florida business filings scraper — SFTP + fixed-width parser."""

from __future__ import annotations

import io
import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

import paramiko

from config import (
    FL_SFTP_HOST, FL_SFTP_PORT, FL_SFTP_USERNAME, FL_SFTP_PASSWORD,
    FL_SFTP_PATH_TEMPLATE, FL_FIELDS, FL_OFFICER_START,
    FL_OFFICER_BLOCK_SIZE, FL_OFFICER_COUNT, FL_OFFICER_FIELDS,
    FL_AGENT_NAME_START, FL_AGENT_NAME_LEN,
)
from states.base import StateScraper

logger = logging.getLogger(__name__)


class FloridaScraper(StateScraper):
    state_code = "FL"
    source_name = "sunbiz_sftp"

    def fetch(self, target_date: date) -> List[Dict[str, Any]]:
        raw_data = self._download_file(target_date)
        if raw_data is None:
            return []
        return self._parse_records(raw_data)

    def _download_file(self, target_date: date) -> Optional[bytes]:
        """Download the daily filing file via SFTP, walking back up to 5 business days."""
        transport = None
        sftp = None
        try:
            transport = paramiko.Transport((FL_SFTP_HOST, FL_SFTP_PORT))
            transport.connect(username=FL_SFTP_USERNAME, password=FL_SFTP_PASSWORD)
            sftp = paramiko.SFTPClient.from_transport(transport)

            current = target_date
            for attempt in range(6):  # target + 5 fallback days
                date_str = current.strftime("%Y%m%d")
                remote_path = FL_SFTP_PATH_TEMPLATE.format(date=date_str)
                logger.info(f"Trying FL SFTP path: {remote_path}")
                try:
                    with io.BytesIO() as buf:
                        sftp.getfo(remote_path, buf)
                        buf.seek(0)
                        data = buf.read()
                    if current != target_date:
                        logger.warning(
                            f"No file for {target_date}, using {current} instead"
                        )
                    logger.info(
                        f"Downloaded FL file for {current} ({len(data)} bytes)"
                    )
                    return data
                except FileNotFoundError:
                    logger.debug(f"No file at {remote_path}")
                # Walk backward, skipping weekends
                current -= timedelta(days=1)
                while current.weekday() >= 5:  # Skip Sat/Sun
                    current -= timedelta(days=1)

            logger.error(
                f"No FL file found within 5 business days of {target_date}"
            )
            return None
        except Exception as e:
            logger.error(f"FL SFTP connection failed: {e}")
            return None
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def _parse_records(self, raw_data: bytes) -> List[Dict[str, Any]]:
        """Parse fixed-width records from the raw file data."""
        text = raw_data.decode("latin-1")
        lines = text.split("\n")
        records = []

        for line_num, line in enumerate(lines, 1):
            if len(line.strip()) == 0:
                continue
            # Pad line to minimum length to avoid index errors
            line = line.ljust(1440)
            try:
                record = self._parse_single_record(line)
                records.append(record)
            except Exception as e:
                logger.warning(f"Failed to parse FL line {line_num}: {e}")

        logger.info(f"Parsed {len(records)} FL records")
        return records

    def _parse_single_record(self, line: str) -> Dict[str, Any]:
        """Parse a single fixed-width line into a dict."""
        record = {}

        # Extract main fields
        for field_name, (start, length) in FL_FIELDS.items():
            record[field_name] = line[start:start + length].strip()

        # Parse filing date from MMDDYYYY to YYYY-MM-DD
        raw_date = record.get("filing_date", "")
        if raw_date and len(raw_date) == 8 and raw_date.isdigit():
            mm, dd, yyyy = raw_date[:2], raw_date[2:4], raw_date[4:]
            record["filing_date"] = f"{yyyy}-{mm}-{dd}"

        # Extract agent/contact name (appears at position 544, separate from officers)
        agent_name_raw = line[FL_AGENT_NAME_START:FL_AGENT_NAME_START + FL_AGENT_NAME_LEN].strip()
        record["agent_name"] = _parse_fl_name(agent_name_raw)

        # Extract officer blocks
        officers = []
        for i in range(FL_OFFICER_COUNT):
            block_start = FL_OFFICER_START + (i * FL_OFFICER_BLOCK_SIZE)
            officer = {}
            for field_name, (offset, length) in FL_OFFICER_FIELDS.items():
                pos = block_start + offset
                officer[field_name] = line[pos:pos + length].strip()
            # Parse the name into readable format
            if officer.get("name"):
                officer["name"] = _parse_fl_name(officer["name"])
                officers.append(officer)

        record["officers"] = officers
        return record


def _parse_fl_name(raw: str) -> str:
    """Parse FL fixed-width name format 'LAST                FIRST       MI' into 'FIRST LAST'."""
    if not raw:
        return ""
    # Name is typically: last (20 chars) + first (20 chars) in a 40-char field
    # Split on multiple spaces to separate parts
    parts = [p for p in raw.split() if p]
    if len(parts) >= 2:
        # Assume first part is last name, second is first name, rest are middle/suffix
        last = parts[0]
        first = parts[1]
        rest = " ".join(parts[2:])
        name = f"{first} {last}"
        if rest:
            name += f" {rest}"
        return name
    return raw
