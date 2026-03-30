"""Configuration constants for the new business entity scraper."""

import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

# Florida SFTP configuration
FL_SFTP_HOST = "sftp.floridados.gov"
FL_SFTP_PORT = 22
FL_SFTP_USERNAME = "Public"
FL_SFTP_PASSWORD = "PubAccess1845!"
FL_SFTP_PATH_TEMPLATE = "/public/doc/cor/{date}c.txt"

# Florida fixed-width field definitions — verified against actual file data.
# (start_position, length)
FL_FIELDS = {
    "corp_number":     (0, 12),
    "corp_name":       (12, 192),
    "status":          (204, 1),       # A=Active
    "filing_code":     (205, 4),       # e.g. FLAL, DOMP
    # Registered agent address block (126 chars)
    "ra_address_1":    (220, 40),
    "ra_address_2":    (260, 40),
    "ra_city":         (300, 32),
    "ra_state":        (332, 2),
    "ra_zip":          (334, 10),
    "ra_country":      (344, 2),
    # Principal office address block (126 chars)
    "princ_address_1": (346, 40),
    "princ_address_2": (386, 40),
    "princ_city":      (426, 32),
    "princ_state":     (458, 2),
    "princ_zip":       (460, 10),
    "princ_country":   (470, 2),
    # Filing date and EIN
    "filing_date":     (472, 8),       # MMDDYYYY (no slashes)
    "fei_ein_number":  (480, 14),
}

# Agent/contact name block at position 540 (not a titled officer)
FL_AGENT_NAME_START = 544
FL_AGENT_NAME_LEN = 40

# Officer blocks: 6 slots, each 128 chars, starting at position 668
FL_OFFICER_START = 668
FL_OFFICER_BLOCK_SIZE = 128
FL_OFFICER_COUNT = 6
FL_OFFICER_FIELDS = {
    "title":   (0, 4),
    "name":    (5, 40),      # skip 1-char flag at offset 4
    "address": (47, 40),     # skip 2-char gap after name
    "city":    (89, 28),
    "state":   (117, 2),
    "zip":     (119, 9),
}

# Florida status codes
FL_STATUS_ACTIVE = "A"

# New York API configuration
NY_FILINGS_URL = "https://data.ny.gov/resource/k4vb-judh.json"
NY_ADDRESS_URL = "https://data.ny.gov/resource/2tms-hftb.json"
NY_API_LIMIT = 50000

# Output CSV columns (in order)
CSV_COLUMNS = [
    "source_state",
    "entity_name",
    "entity_number",
    "entity_type",
    "filing_date",
    "status",
    "contact_name",
    "contact_title",
    "mail_address_line1",
    "mail_address_line2",
    "mail_city",
    "mail_state",
    "mail_zip",
    "principal_address",
    "ein",
    "registered_agent_address",
    "source",
    "scraped_at",
]
