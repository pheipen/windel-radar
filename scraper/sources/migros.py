"""Migros: bot protection blocks plain requests (checked 2026-10-20); tried each run in case that changes."""
from common import ldjson_scrape

NAME = "Migros"


def scrape():
    return ldjson_scrape(NAME, "https://www.migros.ch/de/search?query=pampers")
