# builders/builder_over_15.py
from __future__ import annotations

from typing import Any, Dict, List

from .common import (
    is_fixture_playable,
    build_odds_index,
    get_market_odds,
    build_leg,
)

BET_NAME = "Goals Over/Under"
VALUE_LABEL = "Over 1.5"
MARKET_CODE = "O15"
MARKET_FAMILY = "GOALS"
PICK_LABEL = "Over 1.5 Goals"


def build_over_15_legs(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    max_legs: int = 100,
) -> List[Dict[str, Any]]:
    """
    Builder za Total Goals Over 1.5.
    """
    if not fixtures or not odds:
        return []

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

    # sortiraj po kickoff-u pa po kvoti (veća kvota prvo)
    legs_sorted = sorted(legs, key=lambda x: (x["kickoff"], -x["odds"]))
    return legs_sorted[:max_legs]


def extract_odds(odds_best: dict):
    try:
        return float(odds_best.get("Over/Under", {}).get("Over 1.5"))
    except Exception:
        return None

