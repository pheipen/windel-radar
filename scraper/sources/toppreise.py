"""toppreise.ch: price comparison incl. Galaxus, Brack, Manor, Interdiscount, Coop City, drugstores."""
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common import EXCLUDE, LINES, UA, entry, fetch, parse_count, parse_line, parse_size, text

NAME = "Toppreise"
BASE = "https://www.toppreise.ch"
SHOPS = {"brack.ch ag": "Brack", "interdiscount": "Interdiscount", "galaxus": "Galaxus", "manor": "Manor",
         "coop-city.ch": "Coop City", "digitec": "Digitec"}


def product_urls():
    urls = set()
    queries = [f"pampers {line} {size}" for line in LINES for size in range(1, 9)]
    with ThreadPoolExecutor(4) as pool:
        for page in pool.map(lambda q: fetch(f"{BASE}/produktsuche?q={urllib.parse.quote(q)}"), queries):
            urls |= set(re.findall(r'href="(/preisvergleich/Baby-Kinderpflege/PAMPERS-[^"]+-p\d+)"', page))
    return sorted(u for u in urls if not EXCLUDE.search(u))


def offers(page):
    """(shop, offer name, price, shipping, link) per offer on a product page."""
    for block in re.split(r'<div id="Plugin_Offer_', page)[1:]:
        name = re.search(r'class="offer-name">(.*?)</a>', block, re.S)
        shop = re.search(r'Plugin_ShopLogo.*?alt="([^"]*)"', block, re.S)
        link = re.search(r'data-link="([^"]+)"', block)
        t = text(block[block.find("productPrice"):])
        price = re.search(r"CHF\s*([\d']+\.\d\d)", t)
        ship = re.search(r"Versand:\s*([\d']+\.\d\d)", t)
        if not (name and shop and price and link):
            continue
        num = lambda m: float(m.group(1).replace("'", ""))
        yield (shop.group(1).strip(), text(name.group(1)), num(price), num(ship) if ship else None,
               BASE + text(link.group(1)))


def parse_product(url, page):
    title = text(" ".join(re.findall(r'<span class="title break">(.*?)</span>', page)[:1]))
    if not title or EXCLUDE.search(title):
        return []
    t_size, t_count, t_line = parse_size(title), parse_count(title), parse_line(title)
    found = list(offers(page))
    if t_count is None:  # title without count: use it only if all offers that name a count agree
        named = {parse_count(o[1]) for o in found} - {None}
        t_count = named.pop() if len(named) == 1 else None
    rows = []
    for shop, name, price, ship, link in found:
        if EXCLUDE.search(name):
            continue
        o_size, o_count = parse_size(name), parse_count(name)
        if (o_size and t_size and o_size != t_size) or (o_count and t_count and o_count != t_count):
            continue  # shop text contradicts toppreise's product -> skip rather than guess
        line = t_line if t_line != "Andere" else parse_line(name)
        store = SHOPS.get(shop.lower(), shop)
        row = entry(store, f"Pampers {title}", price, t_count or o_count, t_size or o_size, line, link,
                    shipping=ship, source=NAME)
        if row:
            row["product_url"] = BASE + url
            rows.append(row)
    return rows


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def shop_link(row):
    """toppreise's /ext_de link expires; resolve it to the shop's own URL now."""
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(urllib.request.Request(row["url"], headers={"User-Agent": UA}), timeout=20)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        if loc.startswith("http"):
            return loc
    except Exception:
        pass
    return row["product_url"]  # fallback: toppreise product page


def scrape():
    urls = product_urls()
    if not urls:
        raise RuntimeError("keine Produkte gefunden")
    with ThreadPoolExecutor(4) as pool:
        pages = list(pool.map(lambda u: fetch(BASE + u), urls))
    rows = [r for u, p in zip(urls, pages) for r in parse_product(u, p)]
    with ThreadPoolExecutor(6) as pool:
        for row, link in zip(rows, pool.map(shop_link, rows)):
            row["url"] = link
            del row["product_url"]
    return rows
