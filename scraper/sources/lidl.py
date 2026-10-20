"""Lidl Schweiz: weekly offers. Often 'diverse Sorten' without size -> dropped by entry()."""
import html
import json
import re

from common import EXCLUDE, entry, fetch, parse_count, parse_line, parse_size, text

NAME = "Lidl"


def parse(page):
    rows = []
    for raw in re.findall(r'data-grid-data="(\{.*?\})"', page):
        try:
            d = json.loads(html.unescape(raw))
        except ValueError:
            continue
        title = d.get("fullTitle", "")
        if (d.get("brand") or {}).get("name", "").lower() != "pampers" or EXCLUDE.search(title):
            continue
        facts = text((d.get("keyfacts") or {}).get("description", ""))
        price = d.get("price") or {}
        old = price.get("oldPrice") or 0
        promo = f"statt CHF {old:.2f}" if old > price.get("price", 0) else "Aktion (Filiale)"
        info = f"{title} {facts}"
        row = entry(NAME, title, price.get("price"), parse_count(info), parse_size(info), parse_line(title),
                    "https://www.lidl.ch" + d.get("canonicalUrl", ""), promo=promo)
        if row:
            rows.append(row)
    return rows


def scrape():
    return parse(fetch("https://www.lidl.ch/q/de-CH/search?q=pampers"))
