"""Denner: search lists its Pampers promotions; each product page has ld+json price, 'statt' and the promo dates."""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from common import EXCLUDE, entry, fetch, ldjson_products, parse_count, parse_line, parse_size, text

NAME = "Denner"
BASE = "https://www.denner.ch"


def parse(page, url, today):
    prices = ldjson_products(page)
    desc = re.search(r'"@type":"Product".*?"description":"([^"]*)"', page)  # size + count live here
    if not prices:
        return None
    title = text(html.unescape(f"{prices[0][0]} {desc.group(1) if desc else ''}"))
    if EXCLUDE.search(title) or "pampers" not in title.lower() and "pingo" not in title.lower():
        return None
    price = prices[0][2]
    old = re.search(r'price-tag__instead[^>]*>statt ([\d.]+)', page)
    span = re.search(r"(\d{2})\.(\d{2})\.\s*[–-]\s*(\d{2})\.(\d{2})\.(\d{4}) in Aktion", page)
    frm = until = None
    if span:
        d1, m1, d2, m2, y = span.groups()
        frm, until = f"{int(y) - (m1 > m2)}-{m1}-{d1}", f"{y}-{m2}-{d2}"
        if until < today:
            return None
    promo = f"statt CHF {float(old.group(1)):.2f}" if old and float(old.group(1)) > price else None
    return entry(NAME, title, price, parse_count(title), parse_size(title), parse_line(title), url,
                 promo=promo, where="filiale", valid_from=frm, valid_until=until)


def scrape():
    links = []
    for q in ("pampers", "pingo"):
        found = re.findall(r'href="(/de/[^"]*~p\d+[^"]*)"', fetch(f"{BASE}/de/search?q={q}"))
        links += [BASE + html.unescape(l) for l in found if re.search(r"pampers|pingo", l) and BASE + html.unescape(l) not in links]
    with ThreadPoolExecutor(4) as pool:
        pages = list(pool.map(fetch, links))
    today = date.today().isoformat()
    return [r for u, p in zip(links, pages) if (r := parse(p, u, today))]
