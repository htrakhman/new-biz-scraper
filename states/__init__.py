from .florida import FloridaScraper
from .new_york import NewYorkScraper

STATE_SCRAPERS = {
    "FL": FloridaScraper,
    "NY": NewYorkScraper,
}
