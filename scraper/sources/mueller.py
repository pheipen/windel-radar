"""Müller Drogerie (mueller.ch)."""
import re
from concurrent.futures import ThreadPoolExecutor

from common import EXCLUDE, entry, fetch, ldjson_products, parse_count, parse_line, parse_size

NAME = "Müller"
LIST = "https://www.mueller.ch/b/pampers/alle-pampers-artikel/"


def parse_product(name, url, list_price, page):
    p = page.replace('\\"', '"')
    cap = re.search(r'"capacityUnitCode":"PIECE","capacityValue":"(\d+)"', p)
    count = int(cap.group(1)) if cap else None
    if count and parse_count(name) not in (None, count):
        return None
    strike = re.search(r'"strikePrice":\{[^}]*?"value":([\d.]+)', p)
    promo = f"statt CHF {float(strike.group(1)):.2f}" if strike and float(strike.group(1)) > list_price else None
    return entry(NAME, name, list_price, count, parse_size(name), parse_line(name), url, promo=promo)


def scrape():
    # shortcut: reads only the first listing page (9 items today), add paging if it grows past ~30
    items = [i for i in ldjson_products(fetch(LIST)) if not EXCLUDE.search(i[0])]
    if not items:
        raise RuntimeError("keine Produkte gefunden")
    with ThreadPoolExecutor(4) as pool:
        pages = list(pool.map(lambda i: fetch(i[1]), items))
    return [r for (n, u, pr), pg in zip(items, pages) if (r := parse_product(n, u, pr, pg))]
