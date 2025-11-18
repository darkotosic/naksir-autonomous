# builders/builder_btts.py
from __future__ import annotations

from typing import Any, Dict, List

from .builder_btts_yes import build_btts_yes_legs


def build_btts_legs(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    max_legs: int = 100,
) -> List[Dict[str, Any]]:
    """
    Legacy wrapper: BTTS == BTTS_YES.

    Zadržano samo da ne puknu stari importi.
    Novi kod treba direktno da koristi build_btts_yes_legs
    ili build_btts_no_legs preko registry-ja.
    """
    return build_btts_yes_legs(fixtures, odds, max_legs=max_legs)
