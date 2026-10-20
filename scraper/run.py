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
SOURCES = ["toppreise", "mueller", "lidl", "aktionis", "coop", "migros", "aldi"]
ZH = ZoneInfo("Europe/Zurich")


def run_sources():
    items, hints, status = [], [], []
    for mod_name in SOURCES:
        mod = importlib.import_module(f"sources.{mod_name}")
        try:
            rows = mod.scrape()
            hints += [r for r in rows if r.get("hint")]
            items += [r for r in rows if not r.get("hint")]
            status.append({"name": mod.NAME, "ok": True, "count": len(rows)})
        except Exception as e:
            traceback.print_exc()
            status.append({"name": mod.NAME, "ok": False, "error": str(e)[:200]})
        print(status[-1], flush=True)
    seen, unique = set(), []
    for r in sorted(items, key=lambda r: r["ppd"]):
        key = (r["store"].lower(), r["size"], r["count"], r["line"], r["price"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique, hints, status


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
    items, hints, status = run_sources()
    now = datetime.now(ZH)
    DATA.mkdir(exist_ok=True)
    (DATA / "prices.json").write_text(json.dumps(
        {"updated": now.isoformat(timespec="minutes"), "sources": status, "items": items, "hints": hints},
        ensure_ascii=False, indent=1))
    hist_file = DATA / "history.json"
    history = json.loads(hist_file.read_text()) if hist_file.exists() else {}
    hist_file.write_text(json.dumps(update_history(history, items, now.date().isoformat()),
                                    ensure_ascii=False, indent=1))
    print(f"{len(items)} Einträge")
    if not items:
        sys.exit("keine Preise gefunden")  # fail the Action so it shows up red


if __name__ == "__main__":
    main()
