"""Normalize raw state data into the common CSV schema."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

import pandas as pd

from config import CSV_COLUMNS

logger = logging.getLogger(__name__)


def normalize_all(
    fl_records: List[Dict[str, Any]],
    ny_records: List[Dict[str, Any]],
) -> pd.DataFrame:
    """Normalize FL and NY records into a single DataFrame with the common schema."""
    rows = []
    for rec in fl_records:
        rows.append(_normalize_fl(rec))
    for rec in ny_records:
        rows.append(_normalize_ny(rec))

    if not rows:
        return pd.DataFrame(columns=CSV_COLUMNS)

    df = pd.DataFrame(rows, columns=CSV_COLUMNS)

    # Dedup by entity_number + source_state
    before = len(df)
    df = df.drop_duplicates(subset=["entity_number", "source_state"], keep="first")
    dupes = before - len(df)
    if dupes:
        logger.info(f"Removed {dupes} duplicate records")

    return df


def _normalize_fl(rec: Dict[str, Any]) -> List:
    """Map a Florida raw record to the CSV row."""
    now = datetime.now(timezone.utc).isoformat()

    # Address priority: mailing > principal > registered agent
    mail_addr1, mail_addr2, mail_city, mail_state, mail_zip = _fl_best_address(rec)

    # Primary contact: prefer agent name, fall back to first officer
    contact_name = rec.get("agent_name", "")
    officers = rec.get("officers", [])
    contact_title = officers[0].get("title", "") if officers else ""
    if not contact_name and officers:
        contact_name = officers[0].get("name", "")

    # Build composite addresses
    principal_address = _join_address(
        rec.get("princ_address_1", ""),
        rec.get("princ_address_2", ""),
        rec.get("princ_city", ""),
        rec.get("princ_state", ""),
        rec.get("princ_zip", ""),
    )
    ra_address = _join_address(
        rec.get("ra_address_1", ""),
        rec.get("ra_address_2", ""),
        rec.get("ra_city", ""),
        rec.get("ra_state", ""),
        rec.get("ra_zip", ""),
    )

    # Map filing code to human-readable type
    entity_type = _fl_entity_type(rec.get("filing_code", ""))
    status = "Active" if rec.get("status") == "A" else rec.get("status", "")

    return [
        "FL",                              # source_state
        rec.get("corp_name", ""),          # entity_name
        rec.get("corp_number", ""),        # entity_number
        entity_type,                       # entity_type
        rec.get("filing_date", ""),        # filing_date
        status,                            # status
        contact_name,                      # contact_name
        contact_title,                     # contact_title
        mail_addr1,                        # mail_address_line1
        mail_addr2,                        # mail_address_line2
        mail_city,                         # mail_city
        mail_state,                        # mail_state
        mail_zip,                          # mail_zip
        principal_address,                 # principal_address
        rec.get("fei_ein_number", ""),     # ein
        ra_address,                        # registered_agent_address
        "sunbiz_sftp",                     # source
        now,                               # scraped_at
    ]


def _normalize_ny(rec: Dict[str, Any]) -> List:
    """Map a New York raw record to the CSV row."""
    now = datetime.now(timezone.utc).isoformat()

    # Parse filing date
    filing_date = rec.get("filing_date", "")
    if "T" in filing_date:
        filing_date = filing_date.split("T")[0]

    return [
        "NY",                                       # source_state
        rec.get("corp_name", ""),                   # entity_name
        rec.get("dos_id", ""),                      # entity_number
        rec.get("entity_type", ""),                 # entity_type
        filing_date,                                # filing_date
        "",                                         # status (not in NY API)
        rec.get("filer_name", ""),                  # contact_name
        "",                                         # contact_title
        rec.get("filer_addr1", ""),                 # mail_address_line1
        rec.get("filer_addr2", ""),                 # mail_address_line2
        rec.get("filer_city", ""),                  # mail_city
        rec.get("filer_state", ""),                 # mail_state
        rec.get("filer_zip5", ""),                  # mail_zip
        "",                                         # principal_address
        "",                                         # ein
        "",                                         # registered_agent_address
        "data_ny_gov",                              # source
        now,                                        # scraped_at
    ]


def _fl_best_address(rec: Dict) -> tuple:
    """Return (addr1, addr2, city, state, zip) using principal > RA priority.

    The daily file doesn't include a separate mailing address block,
    so we prefer principal office address, then registered agent address.
    """
    for prefix in ("princ_", "ra_"):
        addr1 = rec.get(f"{prefix}address_1", "")
        city = rec.get(f"{prefix}city", "")
        if addr1 or city:
            return (
                addr1,
                rec.get(f"{prefix}address_2", ""),
                city,
                rec.get(f"{prefix}state", ""),
                rec.get(f"{prefix}zip", ""),
            )
    return ("", "", "", "", "")



def _join_address(*parts: str) -> str:
    """Join non-empty address parts with ', '."""
    return ", ".join(p for p in parts if p)


def _fl_entity_type(code: str) -> str:
    """Map FL 4-char filing codes to human-readable types."""
    types = {
        "FLAL": "Florida LLC",
        "DOMP": "Domestic Profit Corporation",
        "DOMN": "Domestic Non-Profit Corporation",
        "FORL": "Foreign LLC",
        "FORP": "Foreign Profit Corporation",
        "FORN": "Foreign Non-Profit Corporation",
        "FLLP": "Florida Limited Partnership",
        "FORLP": "Foreign Limited Partnership",
    }
    return types.get(code, code)
