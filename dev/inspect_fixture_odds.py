#!/usr/bin/env python
from __future__ import annotations
import sys
from datetime import date
from core_data.cache import read_json

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m dev.inspect_fixture_odds <fixture_id>")
        return

    fx_id = int(sys.argv[1])
    today = date.today().isoformat()

    odds = read_json(today, "odds.json")
    rows = [r for r in odds if r.get("fixture_id") == fx_id]
    print(f"[DEV] fixture_id={fx_id} rows={len(rows)}")
    for r in rows[:200]:
        print(
            f"bookmaker={r['bookmaker']!r} | "
            f"bet_name={r['bet_name']!r} | "
            f"label={r['label']!r} | "
            f"market={r['market']!r} | "
            f"odd={r['odd']}"
        )

if __name__ == "__main__":
    main()
