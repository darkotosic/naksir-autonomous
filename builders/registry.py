# builders/registry.py
from __future__ import annotations

from typing import Callable, Dict, List, Any

from .builder_over_25 import build_over_25_legs
from .builder_ht_over_05 import build_ht_over_05_legs
from .builder_under_35 import build_under_35_legs
from .builder_home_win import build_home_win_legs
from .builder_btts import build_btts_legs
from .builder_1X import build_1x_legs
from .builder_X2 import build_x2_legs


BuilderFn = Callable[[List[dict], List[dict], int], List[dict]]


BUILDERS: Dict[str, BuilderFn] = {
    "O25": build_over_25_legs,
    "HT_O05": build_ht_over_05_legs,
    "U35": build_under_35_legs,
    "HOME": build_home_win_legs,
    "BTTS": build_btts_legs,
    "DC_1X": build_1x_legs,
    "DC_X2": build_x2_legs,
}

MARKET_FAMILY: Dict[str, str] = {
    "O25": "GOALS",
    "HT_O05": "HT_GOALS",
    "U35": "GOALS_UNDER",
    "HOME": "RESULT",
    "BTTS": "BTTS",
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
