"""Self-check for promo parsing with cards in aktionis.ch markup: python3 scraper/test_aktionis.py"""
from sources.aktionis import multibuy, parse, where


def card(store, title, desc="", new="", old="", pct="", dates=""):
    return (f'1" class="card"><a href="/deals/x"><div class="card-merchant"><img alt="{store}" /></div>'
            f'<span class="price-new">{new}</span><span class="price-old">{old}</span>'
            f'<span class="price-discount" title="Rabatt">{pct}</span>'
            f'<h3 class="card-title text-truncate">{title}</h3><p class="card-description text-truncate">{desc}</p>'
            f'<span class="card-date">{dates}</span></a>')


SHOP = "<p>Dieses Angebot ist ausschliesslich in den unten aufgeführten Filialen von Migros erhältlich, keine Online-Bestellung.</p>"

# 3 für 2: all three ways aktionis may show the price give the same per-pack price
for shown in (29.97, 44.95, 89.90):
    unit, packs, label = multibuy("Pampers 3 für 2", shown, 44.95)
    assert packs == 3 and abs(unit - 29.97) < 0.02 and label == "3 für 2", (shown, unit)
assert multibuy("Pampers 3 für 2", 10.0, 44.95) is None  # doesn't add up -> no price
assert multibuy("Pampers 3 für 2", 29.97, None) is None
assert multibuy("Ab 2 Stück, z.B. ...", 17.9, 25.6) == (17.9, 2, "ab 2 Stück")
assert multibuy("Pampers Baby-Dry", 20.0, 25.0) == (20.0, 1, None)

assert where(SHOP) == "filiale"
assert where("<p>Dieses Angebot ist im Webshop von Coop Megastore sowie in ausgewählten Filialen erhältlich.</p>") == "online+filiale"

# Migros: whole range, example product, price only in text, date only in text
rows = parse(card("Migros", "Gesamtes Pampers Sortiment",
                  "Ab 2 Stück, (ohne Feuchttücher), z.B. Baby-Dry Grösse 4, 2 x 46 Stück, 17.90 statt 25.60, "
                  "Angebot gilt nur vom 22.10. bis 28.10.2026, solange Vorrat.", pct="30%"), SHOP, "2026-10-22")
hint = [r for r in rows if r.get("hint")]
row = [r for r in rows if not r.get("hint")]
assert len(hint) == 1 and hint[0]["size"] is None and hint[0]["where"] == "filiale", hint
assert len(row) == 1, rows
r = row[0]
assert (r["size"], r["count"], r["min_packs"], r["where"]) == ("4", 92, 2, "filiale"), r
assert (r["valid_from"], r["valid_until"]) == ("2026-10-22", "2026-10-28"), r
assert abs(r["ppd"] - 17.90 / 92) < 1e-4 and "ab 2 Stück" in r["promo"], r

# Coop 3 für 2 with card dates
rows = parse(card("Coop", "Pampers Baby-Dry Pants Grösse 5, 3 für 2", new="29.97", old="44.95",
                  dates="20.10.2026 - 26.10.2026"), "", "2026-10-20")
# no count in that title -> only a hint, never a guessed price
assert all(r.get("hint") for r in rows), rows

rows = parse(card("Coop", "Pampers Baby-Dry Pants Gr. 5, 22 Stück, 3 für 2", new="44.95", old="44.95",
                  dates="20.10.2026 - 26.10.2026"), "", "2026-10-20")
assert len(rows) == 1 and rows[0]["min_packs"] == 3 and abs(rows[0]["ppd"] - 29.97 / 22) < 1e-3, rows

# expired deals disappear, wipes too
assert parse(card("Coop", "Pampers Baby-Dry Gr. 4, 46 Stück", new="15.95", old="19.95",
                  dates="01.10.2026 - 07.10.2026"), "", "2026-10-20") is None
assert parse(card("Coop", "Pampers Fresh & Clean 12x80 Stück", new="29.70", old="59.40"), "", "2026-10-20") is None
print("ok aktionis")
