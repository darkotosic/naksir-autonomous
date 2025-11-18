# builders/builder_btts_yes.py
from __future__ import annotations

from typing import Any, Dict, List

from .common import (
    is_fixture_playable,
    build_odds_index,
    get_market_odds,
    build_leg,
)

BET_NAME = "Both Teams to Score"
VALUE_LABEL = "Yes"

MARKET_CODE = "BTTS_YES"
MARKET_FAMILY = "BTTS"
PICK_LABEL = "Both Teams to Score – Yes"


def build_btts_yes_legs(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    max_legs: int = 100,
) -> List[Dict[str, Any]]:
    """
    Builder za BTTS Yes (oba tima daju gol).
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

    # sortiraj po kickoff-u (rastuce) pa po kvoti (opadajuće)
    legs_sorted = sorted(legs, key=lambda x: (x["kickoff"], -x["odds"]))
    return legs_sorted[:max_legs]
