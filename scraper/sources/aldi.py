"""Aldi Suisse: the commerce API behind aldi-suisse.ch (the website itself is behind Akamai, the API is not)."""
import json

from common import EXCLUDE, entry, fetch, parse_count, parse_line, parse_size

NAME = "Aldi"
API = "https://asl.api.aldi-suisse.ch/commerce/v3/product-search?currency=CHF&serviceType=walk-in&servicePoint=E172"


def parse(found):
    rows = []
    for x in found.get("data", []):
        brand = (x.get("brandName") or "").lower()
        title = f"{x.get('brandName', '')} {x.get('name', '')} {x.get('sellingSize') or ''}".strip()
        if brand not in ("pampers", "pingo") or EXCLUDE.search(title):
            continue
        p = x.get("price") or {}
        price = (p.get("amountRelevant") or 0) / 100
        was = p.get("wasPriceDisplay")
        url = f"https://www.aldi-suisse.ch/de/produkt/{x.get('urlSlugText')}-{x.get('sku')}"
        extra = {"where": "filiale", "valid_from": x.get("onSaleDate")}
        row = entry(NAME, title, price, parse_count(title), parse_size(title), parse_line(title), url,
                    promo=f"statt {was}" if was else None, **extra)
        # 'Maxi-Pack' without size/count: show as hint rather than guess
        rows.append(row or {"hint": True, "store": NAME, "url": url, "size": parse_size(title),
                            "line": parse_line(title), "brand": "Pingo" if brand == "pingo" else "Pampers",
                            "discount": None, "valid_until": None, **extra,
                            "text": f"{title}: {p.get('amountRelevantDisplay', '')}, {x.get('onSaleDateDisplay') or ''}"})
    return rows


def scrape():
    rows, seen = [], set()
    for q in ("pampers", "pingo"):
        found = json.loads(fetch(f"{API}&q={q}&limit=60&offset=0"))
        if "data" not in found:
            raise RuntimeError(f"unerwartete Antwort: {str(found)[:100]}")
        found["data"] = [x for x in found["data"] if x.get("sku") not in seen]
        seen |= {x.get("sku") for x in found["data"]}
        rows += parse(found)
    return rows
