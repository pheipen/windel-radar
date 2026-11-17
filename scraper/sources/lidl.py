"""Lidl Schweiz: weekly offers. Offers without size ('diverse Sorten') become hints."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from common import EXCLUDE, entry, fetch, parse_count, parse_line, parse_size, text

NAME = "Lidl"


def parse(found):
    """found = the search API's answer; offers live in items[].gridbox.data."""
    rows = []
    for d in (i.get("gridbox", {}).get("data", {}) for i in found.get("items", [])):
        title = d.get("fullTitle", "")
        if (d.get("brand") or {}).get("name", "").lower() != "pampers" or EXCLUDE.search(title):
            continue
        facts = text((d.get("keyfacts") or {}).get("description", ""))
        price = d.get("price") or {}
        old = price.get("oldPrice") or 0
        promo = f"statt CHF {old:.2f}" if old > price.get("price", 0) else "Aktion (Filiale)"
        info = f"{title} {facts}"
        stock = d.get("stockAvailability") or {}
        start = (stock.get("badgeInfoV2") or [{}])[0].get("validFrom")
        extra = {"where": "online+filiale" if stock.get("onlineAvailable") else "filiale",
                 "valid_from": datetime.fromtimestamp(start, ZoneInfo("Europe/Zurich")).date().isoformat()
                 if start else None}
        url = "https://www.lidl.ch" + d.get("canonicalUrl", "")
        row = entry(NAME, title, price.get("price"), parse_count(info), parse_size(info), parse_line(title),
                    url, promo=promo, **extra)
        rows.append(row or {"hint": True, "store": NAME, "url": url, "size": parse_size(info),
                            "line": parse_line(title), "brand": "Pampers", "discount": None, "valid_until": None, **extra,
                            "text": f"{title}: CHF {price.get('price', 0):.2f}, {facts}"})
    return rows


def scrape():
    # the HTML search answers 404 when nothing matches; the JSON API says {"type": "empty"} instead
    found = json.loads(fetch("https://www.lidl.ch/q/api/search?q=pampers&locale=de_CH&assortment=CH&version=2.1.0"))
    if found.get("type") not in ("search", "empty"):
        raise RuntimeError(f"unerwartete Antwort: {found.get('type')}")
    return parse(found)
