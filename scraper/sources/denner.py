"""Denner: Pampers only show up as weekly promotions."""
import re

from common import fetch

NAME = "Denner"


def scrape():
    page = fetch("https://www.denner.ch/de/search?q=pampers")
    hits = re.findall(r'href="(/de/aktionen/[^"]*pampers[^"]*)"', page, re.I)
    if hits:
        # shortcut: no Pampers promo was live when this was written, so the price markup is unknown;
        # report it so the parser gets written when one shows up
        raise RuntimeError(f"Pampers-Aktion gefunden, Preis noch nicht auslesbar: {hits[0]}")
    return []
