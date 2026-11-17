#!/bin/zsh
# Main scraper on Philipp's Mac (launchd ch.pheipen.windel-radar): pull, scrape, commit data/, push.
# Log: ~/Library/Logs/windel-radar.log. On failure: macOS notification.
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${0:A:h}/.." || exit 1
exec >>"$HOME/Library/Logs/windel-radar.log" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') start"

fail() {
  echo "FEHLER: $1"
  osascript -e "display notification \"$1\" with title \"Windel-Radar\" subtitle \"Preise holen fehlgeschlagen\" sound name \"Basso\""
  exit 1
}

# right after wake-up the network may not be back yet
for i in {1..30}; do curl -s -m 5 -o /dev/null https://github.com && break; sleep 5; done

git pull -q --rebase --autostash || fail "git pull ging nicht"
for attempt in 1 2; do
  python3 scraper/run.py; code=$?
  git add data
  git diff --cached --quiet || git commit -q -m "Preise $(date '+%Y-%m-%d %H:%M') (Mac)" || fail "git commit ging nicht"
  git push -q && break
  # the Action pushed in between: drop our data commit, take theirs, scrape again on top of it
  [[ $attempt == 2 ]] && fail "git push ging nicht"
  git fetch -q && git reset -q --keep origin/main || fail "git reset ging nicht"
done
[[ $code == 0 ]] || fail "seit über 24 h keine frischen Preise (siehe Log)"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ok"
