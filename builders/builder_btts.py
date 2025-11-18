# builders/builder_btts.py
from __future__ import annotations

from typing import Any, Dict, List

from .common import (
    is_fixture_playable,
    build_odds_index,
    get_market_odds,
    build_leg,
)

BET_NAME = "Both Teams to Score"
VALUE_LABEL_YES = "Yes"

MARKET_CODE = "BTTS"
MARKET_FAMILY = "BTTS"
PICK_LABEL_YES = "Both Teams to Score – Yes"


def build_btts_legs(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    max_legs: int = 100,
) -> List[Dict[str, Any]]:
    """
    Gradnja BTTS (Both Teams to Score – Yes) legova u standardizovanom formatu.

    Ulaz:
        fixtures: lista clean-ovanih fixtures (output iz clean_fixtures)
        odds: lista clean-ovanih odds (output iz clean_odds)
        max_legs: maksimalan broj legova koje vraćamo

    Izlaz:
        lista leg dict-ova kompatibilnih sa build_leg / engine-om.
    """
    if not fixtures or not odds:
        return []

    odds_index = build_odds_index(odds)
    legs: List[Dict[str, Any]] = []

    for fx in fixtures:
        # Globalni sanity check (liga, status, itd.)
        if not is_fixture_playable(fx):
            continue

        fixture = fx.get("fixture") or {}
        fid = fixture.get("id")
        if fid is None:
            continue

        # Uzimamo BTTS Yes kvotu
        odd_val = get_market_odds(odds_index, int(fid), BET_NAME, VALUE_LABEL_YES)
        if odd_val is None:
            continue

        leg = build_leg(
            fx,
            market=MARKET_CODE,
            market_family=MARKET_FAMILY,
            pick=PICK_LABEL_YES,
            odds=odd_val,
        )
        if leg:
            legs.append(leg)

    # Sortiraj po kickoff (rastuce) pa po kvoti (silazno) i limitiraj broj.
    legs_sorted = sorted(legs, key=lambda x: (x["kickoff"], -x["odds"]))
    return legs_sorted[:max_legs]
