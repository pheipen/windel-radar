"""Offline self-check of the source parsers and run.merge: python3 scraper/test_sources.py"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run import merge
from sources import aldi, denner, lidl, migros, toppreise

# Migros product card (shape of /product-display/public/v4/product-cards), one with an 'ab 2 Stück' promotion
card = {"brand": "Pampers", "title": "Pampers Baby Dry · Windeln · Gr.4,9-14kg", "productUrls": "https://www.migros.ch/de/product/1",
        "productAvailability": "ONLINE_AND_INSTORE",
        "offer": {"quantity": "45 Stk.", "price": {"effectiveValue": 19.95},
                  "promotionPrice": {"effectiveValue": 13.95}, "promotionDateRange": {"startDate": "2026-11-12", "endDate": "2026-11-18"},
                  "badges": [{"type": "MINIMUM_PIECES", "description": "Ab 2 Stück"}, {"type": "PERCENTAGE_PROMOTION", "description": "30%"}]}}
wipes = {"brand": "Pampers", "title": "Pampers Feuchttücher Sensitive", "offer": {"quantity": "52 Stk.", "price": {"effectiveValue": 3}}}
(r,) = migros.parse([card, wipes])
assert (r["size"], r["count"], r["price"], r["min_packs"], r["valid_until"]) == ("4", 45, 13.95, 2, "2026-11-18"), r
assert r["promo"] == "Ab 2 Stück · statt CHF 19.95 · 30%" and r["where"] == "online+filiale"
night = dict(card, title="Pampers · Night Pants · Gr.5, 11-17 kg", offer={"quantity": "35 Stk", "price": {"effectiveValue": 19.95}})
assert migros.parse([night])[0]["line"] == "Baby-Dry Pants" and migros.parse([night])[0]["promo"] is None

# Denner product page (ld+json with a nonce attribute + price tag + promo dates)
page = ('<script nonce="x" type="application/ld+json" id="json-ld">[{"@type":"Product","brand":{"@type":"Brand","name":"Denner"},'
        '"name":"Pampers Baby-Dry Windeln","description":"Grösse 3, 6–10 kg, 52 Stück","offers":{"@type":"Offer","price":9.95}}]</script>'
        '<span class="price-tag__instead" data-v-1>statt 19.90</span> 05.11.–09.12.2026 in Aktion')
r = denner.parse(page, "https://www.denner.ch/de/aktionen/x~p1", "2026-11-17")
assert (r["size"], r["count"], r["price"], r["promo"], r["valid_from"], r["valid_until"]) == \
    ("3", 52, 9.95, "statt CHF 19.90", "2026-11-05", "2026-12-09"), r
assert denner.parse(page, "u", "2026-12-10") is None  # promo over

# Aldi search API: with size+count -> price row, 'Maxi-Pack' without -> hint
found = {"data": [
    {"brandName": "PAMPERS", "name": "Baby-Dry Gr. 4", "sellingSize": "64 Stück", "sku": "1", "urlSlugText": "p",
     "price": {"amountRelevant": 1999, "wasPriceDisplay": "CHF 29.95"}, "onSaleDate": "2026-11-05"},
    {"brandName": "PAMPERS", "name": "Baby-Dry, Maxi-Pack", "sellingSize": None, "sku": "2", "urlSlugText": "q",
     "price": {"amountRelevant": 2499, "amountRelevantDisplay": "CHF 24.99"}},
    {"brandName": "MAMIA", "name": "Baby-Pants, Junior", "sellingSize": "36 Stück", "sku": "3", "price": {"amountRelevant": 499}}]}
row, hint = aldi.parse(found)
assert (row["size"], row["count"], row["price"], row["promo"]) == ("4", 64, 19.99, "statt CHF 29.95"), row
assert hint["hint"] and hint["size"] is None and "24.99" in hint["text"], hint

# Lidl search API: {"type": "empty"} -> nothing; a Pampers item -> row
assert lidl.parse({"type": "empty"}) == []
item = {"gridbox": {"data": {"fullTitle": "Pampers Baby-Dry Gr. 4, 2x 46 Stück", "brand": {"name": "Pampers"},
                             "price": {"price": 19.99, "oldPrice": 29.9}, "canonicalUrl": "/p/x", "stockAvailability": {}}}}
(r,) = lidl.parse({"type": "search", "items": [item]})
assert (r["count"], r["size"], r["promo"]) == (92, "4", "statt CHF 29.90"), r

# Toppreise: listing links in any category
assert toppreise.re.findall(r'href="(/preisvergleich/[^/"]+/(?:PAMPERS|PINGO)-[^"]+-p\d+)"',
                            '<a href="/preisvergleich/Windeln/PAMPERS-Baby-Dry-Groesse-3-p383890">') == \
    ["/preisvergleich/Windeln/PAMPERS-Baby-Dry-Groesse-3-p383890"]

# run.merge: failed source keeps its last rows (with old 'at'), too old / expired rows go, ok sources replace
now, today = "2026-11-17T06:23+01:00", "2026-11-17"
mk = lambda src, at, ppd, **k: {"store": src, "size": "4", "count": 50, "line": "Baby-Dry", "price": ppd * 50,
                                "ppd": ppd, "source": src, "at": at, **k}
old = {"sources": [{"name": "Migros", "ok": True, "at": "2026-11-16T18:23+01:00"}],
       "items": [mk("Migros", "2026-11-16T18:23+01:00", 0.30), mk("Migros", "2026-11-01T18:23+01:00", 0.20),
                 mk("Migros", "2026-11-16T18:23+01:00", 0.25, valid_until="2026-11-16"),
                 mk("Denner", "2026-11-16T18:23+01:00", 0.10)], "hints": []}
status = [{"name": "Migros", "ok": False, "error": "403"}, {"name": "Denner", "ok": True, "count": 1, "at": now}]
items, hints = merge([mk("Denner", now, 0.19)], status, old, now, today)
assert [(r["source"], r["ppd"], r["at"]) for r in items] == \
    [("Denner", 0.19, now), ("Migros", 0.30, "2026-11-16T18:23+01:00")], items
assert status[0]["at"] == "2026-11-16T18:23+01:00" and status[0]["kept"] == 1
print("ok sources")
