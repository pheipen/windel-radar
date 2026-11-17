"""Coop: bot protection blocks plain requests (checked 2026-10-20, still 403 on 2026-11-17 also with headless + visible Chrome); tried each run in case that changes."""
from common import ldjson_scrape

NAME = "Coop"


def scrape():
    return ldjson_scrape(NAME, "https://www.coop.ch/de/search/?text=pampers")
