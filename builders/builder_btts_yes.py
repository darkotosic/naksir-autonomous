# builders/builder_btts_yes.py
from __future__ import annotations

from typing import Any, Dict, List

from .common import (
    is_fixture_playable,
    build_odds_index,
    get_market_odds_by_code,  # NOVI helper
    build_leg,
)

# Ovaj builder gađa canonical market kod "BTTS_YES"
MARKET_CODE = "BTTS_YES"
MARKET_FAMILY = "BTTS"
PICK_LABEL = "Both Teams to Score – Yes"


def build_btts_yes_legs(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    max_legs: int = 200,
) -> List[Dict[str, Any]]:
    """
    Gradi BTTS YES legove na global pool-u.

    Pravila:
      - fixture mora biti "playable" (nije počeo, ima league_id itd.)
      - koristi canonical 'market' kod iz clean_odds (BTTS_YES)
      - vraća max_legs legova, sortiranih po kickoff -> kvota (veća kvota prvo)
    """
    if not fixtures or not odds:
        return []

    odds_index = build_odds_index(odds)
    legs: List[Dict[str, Any]] = []

    for fx in fixtures:
        if not is_fixture_playable(fx):
            continue

        fixture_block = fx.get("fixture") or {}
        fid = fixture_block.get("id")
        if not fid:
            continue

        odd_val = get_market_odds_by_code(odds_index, int(fid), MARKET_CODE)
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

    # sortiraj po kickoff-u (rastuce) pa po kvoti (opadajuće = value first)
    legs_sorted = sorted(legs, key=lambda x: (x["kickoff"], -x["odds"]))
    return legs_sorted[:max_legs]


def extract_odds(odds_best: dict):
    """
    Legacy helper ako koristiš ovaj builder u drugim projektima koji rade sa
    agregiranim 'odds_best' dict-om po marketu.
    Trenutno ga Naksir autonomous ne koristi direktno, ostavljen radi kompatibilnosti.
    """
    try:
        return float(odds_best.get("BTTS", {}).get("Yes"))
    except Exception:
        return None
