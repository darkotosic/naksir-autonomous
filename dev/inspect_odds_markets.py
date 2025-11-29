#!/usr/bin/env python
from __future__ import annotations
import os, json
from collections import Counter
from datetime import date

from core_data.cache import read_json, CACHE_ROOT

def main():
    today = date.today().isoformat()
    print(f"[DEV] Inspect odds for {today}")

    odds = read_json(today, "odds.json")
    print(f"[DEV] odds rows: {len(odds)}")

    c_market = Counter()
    c_bet = Counter()

    for row in odds:
        c_market[row.get("market") or "NONE"] += 1
        c_bet[(row.get("bet_name") or "").strip().lower()] += 1

    print("\n[DEV] Top markets by 'market' field:")
    for m, cnt in c_market.most_common(30):
        print(f"  {m:10s} -> {cnt}")

    print("\n[DEV] Top bet_name values:")
    for bn, cnt in c_bet.most_common(30):
        print(f"  {bn:40s} -> {cnt}")

if __name__ == "__main__":
    main()
