"""Migros: the JSON API behind migros.ch (guest token, search, product cards). The HTML page has no prices."""
import json
import re
import urllib.request

from common import EXCLUDE, UA, Blocked, entry, parse_count, parse_line, parse_size

NAME = "Migros"
API = "https://www.migros.ch"


def call(path, body=None, token=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"User-Agent": UA, "Accept": "application/json",
                                          "Content-Type": "application/json", "migros-language": "de",
                                          "peer-id": "website-js-800.0.0", **({"leshopch": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.headers.get("leshopch"), json.loads(r.read())
    except Exception as e:
        raise Blocked(f"{type(e).__name__}: {e}") from e


def parse(cards):
    rows = []
    for c in cards:
        title = f"{c.get('title', '')} {c.get('offer', {}).get('quantity', '')}"
        offer = c.get("offer") or {}
        if c.get("brand", "").lower() not in ("pampers", "pingo") or EXCLUDE.search(title):
            continue
        regular = (offer.get("price") or {}).get("effectiveValue")
        promo_price = (offer.get("promotionPrice") or {}).get("effectiveValue")
        badges = {b.get("type"): b.get("description", "") for b in offer.get("badges") or []}
        dates = offer.get("promotionDateRange") or {}
        promo, packs = None, 1
        if promo_price and regular and promo_price < regular:
            m = re.search(r"\d+", badges.get("MINIMUM_PIECES", ""))
            packs = int(m.group()) if m else 1
            promo = " · ".join(x for x in [badges.get("MINIMUM_PIECES"), f"statt CHF {regular:.2f}",
                                            badges.get("PERCENTAGE_PROMOTION")] if x)
        row = entry(NAME, title, promo_price if promo else regular, parse_count(title), parse_size(title),
                    parse_line(title), c.get("productUrls") or f"{API}/de/search?query=pampers", promo=promo,
                    min_packs=packs, where="online+filiale" if "ONLINE" in c.get("productAvailability", "") else "filiale",
                    valid_from=dates.get("startDate") if promo else None,
                    valid_until=dates.get("endDate") if promo else None)
        if row:
            rows.append(row)
    return rows


def scrape():
    token, _ = call("/authentication/public/v1/api/guest?authorizationNotRequired=true")
    ids = []
    for q in ("pampers", "pingo"):
        _, found = call("/onesearch-oc-seaapi/public/v5/search",
                        {"regionId": "national", "language": "de", "productIds": [], "query": q, "sortFields": [],
                         "sortOrder": "asc", "algorithm": "DEFAULT", "filters": {}, "from": 0}, token)
        ids += found.get("productIds", [])
    if not ids:
        raise RuntimeError("Suche ohne Produkte, API geändert?")
    _, cards = call("/product-display/public/v4/product-cards",
                    {"offerFilter": {"storeType": "OFFLINE", "region": "national", "ongoing": True},
                     "productFilter": {"uids": ids}}, token)
    return parse(cards)
