# builders/builder_ht_over_05.py
from __future__ import annotations

from typing import Any, Dict, List

from .common import (
    is_fixture_playable,
    build_odds_index,
    get_market_odds,
    build_leg,
)


BET_NAME = "Goals Over/Under 1st Half"
VALUE_LABEL = "Over 0.5"
MARKET_CODE = "HT_O05"
MARKET_FAMILY = "HT_GOALS"
PICK_LABEL = "HT Over 0.5 Goals"


def build_ht_over_05_legs(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    max_legs: int = 100,
) -> List[Dict[str, Any]]:
    """
    Builder za HT Over 0.5 golova.
    """
    odds_index = build_odds_index(odds)
    legs: List[Dict[str, Any]] = []

    for fx in fixtures or []:
        if not is_fixture_playable(fx):
            continue

        fixture = fx.get("fixture") or {}
        fid = fixture.get("id")
        if fid is None:
            continue

        odd_val = get_market_odds(odds_index, int(fid), BET_NAME, VALUE_LABEL)
        if odd_val is None:
            continue

        leg = build_leg(
            fx,
            market=MARKET_CODE,
            market_family=MARKET_FAMILY,
            pick=PICK_LABEL,
            odds=odd_val,
        )
        if leg:
            legs.append(leg)

    legs_sorted = sorted(legs, key=lambda x: (x["kickoff"], -x["odds"]))
    return legs_sorted[:max_legs]


def extract_odds(odds_best: dict):
    try:
        return float(odds_best.get("HT_Over/Under", {}).get("Over 0.5"))
    except Exception:
        return None

