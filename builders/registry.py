# builders/registry.py
from __future__ import annotations

from typing import Callable, Dict, List, Any

from .builder_over_15 import build_over_15_legs
from .builder_over_25 import build_over_25_legs
from .builder_over_35 import build_over_35_legs
from .builder_under_35 import build_under_35_legs
from .builder_ht_over_05 import build_ht_over_05_legs
from .builder_home_win import build_home_win_legs
from .builder_away_win import build_away_win_legs
from .builder_draw import build_draw_legs
from .builder_btts_yes import build_btts_yes_legs
from .builder_btts_no import build_btts_no_legs
from .builder_btts import build_btts_legs  # legacy alias (BTTS -> YES)
from .builder_1X import build_1x_legs
from .builder_X2 import build_x2_legs


BuilderFn = Callable[[List[dict], List[dict], int], List[dict]]


BUILDERS: Dict[str, BuilderFn] = {
    # Goals markets
    "O15": build_over_15_legs,
    "O25": build_over_25_legs,
    "O35": build_over_35_legs,
    "U35": build_under_35_legs,
    # Match result
    "HOME": build_home_win_legs,
    "AWAY": build_away_win_legs,
    "DRAW": build_draw_legs,
    # BTTS
    "BTTS_YES": build_btts_yes_legs,
    "BTTS_NO": build_btts_no_legs,
    # Legacy alias: zadržavamo "BTTS" kao YES da ne lomimo postojeće setove
    "BTTS": build_btts_legs,
    # Half-time goals
    "HT_O05": build_ht_over_05_legs,
    # Double chance
    "DC_1X": build_1x_legs,
    "DC_X2": build_x2_legs,
}

MARKET_FAMILY: Dict[str, str] = {
    "O15": "GOALS",
    "O25": "GOALS",
    "O35": "GOALS",
    "U35": "GOALS_UNDER",
    "HOME": "RESULT",
    "AWAY": "RESULT",
    "DRAW": "RESULT",
    "BTTS_YES": "BTTS",
    "BTTS_NO": "BTTS",
    "BTTS": "BTTS",           # legacy alias
    "HT_O05": "HT_GOALS",
    "DC_1X": "DOUBLE_CHANCE",
    "DC_X2": "DOUBLE_CHANCE",
}


def get_builder(code: str) -> BuilderFn:
    if code not in BUILDERS:
        raise KeyError(f"Unknown builder code: {code}")
    return BUILDERS[code]


def get_market_family(code: str) -> str:
    if code not in MARKET_FAMILY:
        raise KeyError(f"Unknown market family for code: {code}")
    return MARKET_FAMILY[code]


def list_builders() -> List[str]:
    return sorted(BUILDERS.keys())
