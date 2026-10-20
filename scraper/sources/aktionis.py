"""aktionis.ch: weekly promotions of Coop, Coop Megastore, Migros, Denner, Lidl, OTTO'S, SPAR, Volg (no Aldi)."""
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from common import EXCLUDE, brand_of, entry, fetch, parse_count, parse_line, parse_size, text

NAME = "Aktionis"
BASE = "https://www.aktionis.ch"
STORES = {"lidl": "Lidl", "otto's": "OTTO'S"}


def money(s):
    """'32.15' -> 32.15, '29.–' -> 29.0, '–.80' -> 0.8"""
    s = (s or "").strip().replace("–", "0").replace("-", "0").replace("'", "")
    try:
        return float(s)
    except ValueError:
        return None


def multibuy(t, price, old):
    """Per-pack price and packs to buy for '3 für 2' / 'ab 2 Stück'. None = can't tell for sure.

    aktionis shows either the per-pack price or the price of the whole bundle, so the
    result must match the regular price ('old') to be trusted.
    """
    t = t.lower()
    m = re.search(r"\b(\d)\s*für\s*(\d)\b", t)
    if m and int(m.group(1)) > int(m.group(2)):
        buy, pay = int(m.group(1)), int(m.group(2))
        label = f"{buy} für {pay}"
        if not old:
            return None
        if abs(price - old * pay / buy) <= 0.02 * old:  # already per pack
            return price, buy, label
        if abs(price - old) <= 0.02 * old:  # regular pack price shown
            return price * pay / buy, buy, label
        if abs(price - old * pay) <= 0.02 * old * pay:  # bundle total shown
            return price / buy, buy, label
        return None
    m = re.search(r"\bab\s*(\d)\s*(?:stück|stk|packungen|pack)", t)
    if m and int(m.group(1)) > 1:
        return price, int(m.group(1)), f"ab {m.group(1)} Stück"  # Migros: shown price = per pack when buying n
    return price, 1, None


def where(page):
    """From the sentence 'Dieses Angebot ist ... erhältlich' on the deal page."""
    m = re.search(r"Dieses Angebot ist ([^.|]*)", text(page))
    t = m.group(1).lower() if m else ""
    if "filiale" in t and ("ausschliesslich" in t or "keine online" in t):
        return "filiale"
    if "filiale" in t and ("webshop" in t or "online" in t):
        return "online+filiale"
    if "webshop" in t or "online" in t:
        return "online"
    return "filiale" if "filiale" in t else None


def validity(card, page):
    """(from, until) as ISO dates."""
    until = re.search(r'"priceValidUntil":"([^"]+)"', page)
    if until:
        until = datetime.fromisoformat(until.group(1).replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Zurich"))
        until = until.date().isoformat()
    dates = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", " ".join(re.findall(r'card-date">([^<]*)', card)))
    start = re.search(r"ab (\d{2})\.(\d{2})\.(\d{4}) - Aktionis", page)
    iso = lambda d: f"{d[2]}-{d[1]}-{d[0]}"
    frm = iso(start.groups()) if start else (iso(dates[0]) if dates else None)
    if not until and len(dates) > 1:
        until = iso(dates[1])
    m = re.search(r"vom (\d{1,2})\.(\d{1,2})\.(?:\d{4})? bis (\d{1,2})\.(\d{1,2})\.(\d{4})", text(card))
    if m:  # Migros: 'Angebot gilt nur vom 8.10. bis 21.10.2026'
        d1, m1, d2, m2, y = m.groups()
        y1 = int(y) - (int(m1) > int(m2))  # Dec -> Jan
        frm = frm or f"{y1}-{int(m1):02d}-{int(d1):02d}"
        until = until or f"{y}-{int(m2):02d}-{int(d2):02d}"
    return frm, until


def parse(card, page, today):
    grab = lambda cls: text(" ".join(re.findall(rf'class="{cls}[^"]*"[^>]*>(.*?)</', card, re.S)[:1]))
    title, desc = grab("card-title"), grab("card-description")
    full = re.search(r'"@type":"Product","name":"((?:[^"\\]|\\.)*)"', page)  # card titles get cut with '...'
    if full:
        title = text(json.loads(f'"{full.group(1)}"'))
    if not re.search(r"angebot gilt|z\.\s?b\.|\bab \d|für \d", desc, re.I):
        desc = ""  # product blurb, not deal conditions
    store = text(re.search(r'card-merchant.*?alt="([^"]*)"', card, re.S).group(1))
    store = STORES.get(store.lower(), store)
    link = BASE + re.search(r'href="(/deals/[^"]+)"', card).group(1)
    price, old, pct = money(grab("price-new")), money(grab("price-old")), grab("price-discount")
    detail = text(" ".join(re.findall(r'<meta name="description" content="([^"]*)"', page)))
    info = f"{title} {desc} {detail}"
    frm, until = validity(card, page)
    if until and until < today:
        return None
    base = {"store": store, "url": link, "where": where(page), "valid_from": frm, "valid_until": until,
            "source": NAME}

    # 'z.B.' = the price is only for one example product; the rest of the range has no price for us
    example = re.search(r"z\.\s?b\.\s*(.*?)(?:,\s*[\d–.]+\s*statt|$)", desc, re.I)
    subject = f"{title} {example.group(1)}" if example else title
    # check only the product, not the conditions ('ohne Feuchttücher' must not drop the deal)
    if (not re.search(r"pampers|pingo", info, re.I) or EXCLUDE.search(subject)
            or not re.search(r"windel|pants|grösse|gr\.|size|sortiment", info, re.I)):
        return None
    size, count, line = parse_size(subject), parse_count(subject), parse_line(subject)
    old_from_text = re.search(r"([\d–]+\.[\d–]+)\s*statt\s*([\d–]+\.[\d–]+)", desc)
    if price is None and old_from_text:  # Migros cards: price only in the text
        price, old = money(old_from_text.group(1)), money(old_from_text.group(2))

    rows = []
    if example or not (size and count):
        rows.append({**base, "hint": True, "text": f"{title}: {desc}" if desc else title,
                     "discount": pct or None, "size": parse_size(title), "line": parse_line(title),
                     "brand": brand_of(info)})
    deal = multibuy(info, price, old) if price else None
    if size and count and deal:
        unit, packs, label = deal
        promo = " · ".join(x for x in [label, f"statt CHF {old:.2f}" if old else None, pct or None] if x)
        row = entry(store, title if not example else f"{title} ({example.group(1)})", unit, count, size, line,
                    link, promo=promo or "Aktion", source=NAME, min_packs=packs,
                    **{k: v for k, v in base.items() if k not in ("store", "url", "source")})
        if row:
            rows.append(row)
    return rows


def scrape():
    pages = [fetch(f"{BASE}/deals?q={q}") for q in ("pampers", "pingo")]
    page = "".join(pages)
    cards = re.split(r'<div data-upox-id="', page)[1:]
    if "card-merchant" not in page:
        raise RuntimeError("Seite ohne Aktionen, Aufbau geändert?")
    today = date.today().isoformat()
    rows, seen = [], set()
    for card in cards:
        link = re.search(r'href="(/deals/[^"]+)"', card)
        if not link or link.group(1) in seen:
            continue
        seen.add(link.group(1))
        head = text(" ".join(re.findall(r'class="card-(?:title|description)[^"]*"[^>]*>(.*?)</', card, re.S)))
        if not re.search(r"pampers|pingo", head, re.I):
            continue
        rows += parse(card, fetch(BASE + link.group(1)), today) or []
    return rows
