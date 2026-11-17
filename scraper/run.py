"""Run all sources, write data/prices.json and update data/history.json."""
import importlib
import json
import pathlib
import sys
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
DATA = HERE.parent / "data"
SOURCES = ["toppreise", "migros", "denner", "aldi", "lidl", "aktionis", "mueller", "coop"]
KEEP_DAYS = 7  # a failed source keeps its last prices this long, marked with their time
STALE_HOURS = 24
ZH = ZoneInfo("Europe/Zurich")


def run_sources(now):
    """Each row gets 'source' (module name) and 'at' (when it was fetched)."""
    rows, status = [], []
    for mod_name in SOURCES:
        mod = importlib.import_module(f"sources.{mod_name}")
        try:
            got = mod.scrape()
            rows += [{**r, "source": mod.NAME, "at": now} for r in got]
            status.append({"name": mod.NAME, "ok": True, "count": len(got), "at": now})
        except Exception as e:
            traceback.print_exc()
            status.append({"name": mod.NAME, "ok": False, "error": str(e)[:200]})
        print(status[-1], flush=True)
    return rows, status


def merge(rows, status, old, now, today):
    """Keep the last good rows of every source that failed this run (up to KEEP_DAYS, promos not expired)."""
    cutoff = (datetime.fromisoformat(now) - timedelta(days=KEEP_DAYS)).isoformat(timespec="minutes")
    old_status = {s["name"]: s for s in old.get("sources", [])}
    for s in status:
        if s["ok"]:
            continue
        prev = old_status.get(s["name"], {})
        if prev.get("at"):
            s["at"] = prev["at"]  # last time this source delivered
        kept = [r for r in old.get("items", []) + old.get("hints", [])
                if r.get("source") == s["name"] and r.get("at", "") >= cutoff
                and not (r.get("valid_until") and r["valid_until"] < today)]
        s["kept"] = len(kept)
        rows += kept
    hints = [r for r in rows if r.get("hint")]
    seen, items = set(), []
    for r in sorted((r for r in rows if not r.get("hint")), key=lambda r: (r["ppd"], r["at"] != now)):
        key = (r["store"].lower(), r["size"], r["count"], r["line"], r["price"])
        if key not in seen:
            seen.add(key)
            items.append(r)
    return items, hints


def update_history(history, items, today):
    """Cheapest price per diaper per brand, size and line ('alle' = any line), one point per day, 60 days."""
    if history and "Pampers" not in history:
        history = {"Pampers": history}  # files from before Pingo had no brand level
    for brand in ("Pampers", "Pingo"):
        update_brand(history.setdefault(brand, {}), [r for r in items if r["brand"] == brand], today)
    return history


def update_brand(history, items, today):
    for size in map(str, range(1, 9)):
        for line in ["alle"] + sorted({r["line"] for r in items}):
            rows = [r for r in items if r["size"] == size and line in ("alle", r["line"])]
            if not rows:
                continue
            best = min(rows, key=lambda r: r["ppd"])
            points = history.setdefault(size, {}).setdefault(line, [])
            if points and points[-1]["d"] == today:
                if best["ppd"] >= points[-1]["p"]:
                    continue
                points.pop()
            points.append({"d": today, "p": best["ppd"], "s": best["store"]})
    cutoff = (datetime.now(ZH) - timedelta(days=60)).date().isoformat()
    for lines in history.values():
        for line in lines:
            lines[line] = [p for p in lines[line] if p["d"] >= cutoff]


def main():
    now_dt = datetime.now(ZH)
    now, today = now_dt.isoformat(timespec="minutes"), now_dt.date().isoformat()
    DATA.mkdir(exist_ok=True)
    price_file, hist_file = DATA / "prices.json", DATA / "history.json"
    old = json.loads(price_file.read_text()) if price_file.exists() else {}
    rows, status = run_sources(now)
    items, hints = merge(rows, status, old, now, today)
    fresh_items = [r for r in items if r["at"] == now]
    # 'fresh' = last run that brought in real prices; the page warns when it is older than STALE_HOURS
    fresh = now if fresh_items else old.get("fresh", old.get("updated"))
    price_file.write_text(json.dumps(
        {"updated": now, "fresh": fresh, "sources": status, "items": items, "hints": hints},
        ensure_ascii=False, indent=1))
    history = json.loads(hist_file.read_text()) if hist_file.exists() else {}
    hist_file.write_text(json.dumps(update_history(history, fresh_items, today), ensure_ascii=False, indent=1))
    print(f"{len(items)} Einträge, davon {len(fresh_items)} frisch")
    if not fresh or now_dt - datetime.fromisoformat(fresh) > timedelta(hours=STALE_HOURS):
        sys.exit(f"seit über {STALE_HOURS} h keine frischen Preise")  # red in Actions, notification on the Mac


if __name__ == "__main__":
    main()
