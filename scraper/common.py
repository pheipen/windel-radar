"""Shared helpers: fetching and turning a product name into size, line and count."""
import html
import json
import re
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class Blocked(Exception):
    """Source refuses us (bot protection, 403, timeout)."""


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-CH,de;q=0.9",
                                               "Accept": "text/html,application/xhtml+xml,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:  # HTTPError 403, timeouts, TLS resets
        raise Blocked(f"{type(e).__name__}: {e}") from e


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


# Things that are Pampers but not diapers.
EXCLUDE = re.compile(r"feucht|tücher|tuecher|wipes|splasher|schwimm|creme|lotion|bettunterlage|ninjamas|"
                     r"windeleimer", re.I)

NAMED_SIZES = {"newborn": "1", "new baby": None, "mini": "2", "midi": "3", "maxi plus": None,
               "maxi": "4", "junior": "5", "extra large": "6", "xl": "6"}


def parse_size(s):
    """'Gr. 4', 'Grösse 4', 'Size 4', 'Maxi 4', 'Gr.4' -> '4'. 4+ / 5+ and conflicts -> None."""
    s = s.lower()
    nums = set(re.findall(r"(?:gr\.?|grösse:?|groesse|size|taille)\s*(\d)(?!\d)(\+)?", s))
    if any(plus for _, plus in nums):
        return None  # 4+ / 5+ are separate products; buttons only have 1-8
    found = {n for n, _ in nums}
    if not found:
        # Sizes only named ('Maxi', 'Junior') - only when exactly one name matches
        for name, n in NAMED_SIZES.items():
            if re.search(r"\b" + name + r"\b", s):
                if n is None:
                    return None
                found.add(n)
                break
    if len(found) != 1:
        return None
    n = found.pop()
    return n if "1" <= n <= "8" else None


def parse_count(s):
    """'2x 46 Stück' -> 92, '(Gr. 4, 31 Stk.)' -> 31, '204STK' -> 204. Ambiguous -> None."""
    s = s.lower().replace("×", "x")
    unit = r"(?:stück|stueck|stk\.?|st\.|windeln|pants|pcs|count)"
    if re.search(r"\d+\s*[-–]\s*\d+\s*" + unit, s):
        return None  # '70-132 Stück' = several packs
    multi = re.findall(r"(\d+)\s*x\s*(\d+)\s*" + unit + r"?", s)
    counts = {int(a) * int(b) for a, b in multi if 1 < int(a) <= 12 and int(b) >= 10}
    if not counts:
        counts = {int(n) for n in re.findall(r"(\d+)\s*" + unit + r"(?![a-z])", s)}
    counts = {c for c in counts if 10 <= c <= 400}
    return counts.pop() if len(counts) == 1 else None


LINES = ["Premium Protection Pants", "Baby-Dry Pants", "Premium Protection", "Harmonie", "Baby-Dry"]


def parse_line(s):
    s = s.lower().replace("-", " ")
    pants = "pants" in s
    if "premium" in s:
        return "Premium Protection Pants" if pants else "Premium Protection"
    if "harmonie" in s or "harmony" in s:
        return "Harmonie"
    if "baby dry" in s:
        return "Baby-Dry Pants" if pants else "Baby-Dry"
    return "Andere"


def entry(store, name, price, count, size, line, url, promo=None, shipping=None, source=None):
    """Build one result row, or None if anything looks off (better missing than wrong)."""
    if not (price and count and size) or price <= 0:
        return None
    ppd = (price + (shipping or 0)) / count  # what one diaper really costs when ordering this pack
    if not 0.08 <= ppd <= 1.5:  # sanity range for one diaper in CHF
        return None
    return {"store": store, "name": name, "price": round(price, 2), "count": count, "size": size,
            "line": line, "ppd": round(ppd, 4), "url": url, "promo": promo, "shipping": shipping,
            "source": source or store}


def ldjson_products(page):
    """schema.org Product entries (name, url, price) from ld+json blocks."""
    out = []
    for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d)
            elif isinstance(d, dict):
                if d.get("@type") == "Product" and isinstance(d.get("offers"), dict):
                    try:
                        out.append((d["name"], d.get("url"), float(d["offers"]["price"])))
                    except (KeyError, TypeError, ValueError):
                        pass
                stack.extend(v for v in d.values() if isinstance(v, (dict, list)))
    return out


def ldjson_scrape(store, url):
    """Shops with schema.org data on their search page. No Pampers found = treat as not readable."""
    rows = [entry(store, n, p, parse_count(n), parse_size(n), parse_line(n), u or url)
            for n, u, p in ldjson_products(fetch(url)) if "pampers" in n.lower() and not EXCLUDE.search(n)]
    if not rows:
        raise Blocked("keine Produkte erkannt")
    return [r for r in rows if r]
