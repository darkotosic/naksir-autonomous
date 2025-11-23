# builders/mixer.py
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Tuple, Set, Optional

# Konfiguracija – možeš kasnije da prebaciš u config modul
TARGET_ODDS_MIN_DEFAULT = 2.00
TARGET_ODDS_MAX_DEFAULT = 3.00
LEGS_MIN_DEFAULT = 3
LEGS_MAX_DEFAULT = 5
MAX_FAMILY_PER_TICKET_DEFAULT = 2

# Preferirane lige (možeš da proširiš po potrebi)
ALLOW_LIST: List[int] = [
    2, 3, 913, 5, 536, 808, 960, 10, 667, 29, 30, 31, 32, 37, 33, 34, 848,
    311, 310, 342, 218, 144, 315, 71, 169, 210, 346, 233, 39, 40, 41, 42,
    703, 244, 245, 61, 62, 78, 79, 197, 271, 164, 323, 135, 136, 389, 88,
    89, 408, 103, 104, 106, 94, 283, 235, 286, 287, 322, 140, 141, 113,
    207, 208, 202, 203, 909, 268, 269, 270, 340,
]
ALLOW_SET: Set[int] = set(ALLOW_LIST)


@dataclass
class MarketConfig:
    code: str
    family: str
    bet_name: str
    value_label: str
    pick_label: str


# Definišemo skup tržišta (buildera) koje koristimo u LAYER 2
MARKETS: List[MarketConfig] = [
    MarketConfig(
        code="O15",
        family="GOALS",
        bet_name="Goals Over/Under",
        value_label="Over 1.5",
        pick_label="Over 1.5 Goals",
    ),
    MarketConfig(
        code="O25",
        family="GOALS",
        bet_name="Goals Over/Under",
        value_label="Over 2.5",
        pick_label="Over 2.5 Goals",
    ),
    MarketConfig(
        code="HT_O05",
        family="HT_GOALS",
        bet_name="Goals Over/Under 1st Half",
        value_label="Over 0.5",
        pick_label="HT Over 0.5 Goals",
    ),
    MarketConfig(
        code="U35",
        family="GOALS_UNDER",
        bet_name="Goals Over/Under",
        value_label="Under 3.5",
        pick_label="Under 3.5 Goals",
    ),
    MarketConfig(
        code="HOME",
        family="RESULT",
        bet_name="Match Winner",
        value_label="Home",
        pick_label="Home Win",
    ),
    MarketConfig(
        code="BTTS_YES",
        family="BTTS",
        bet_name="Both Teams To Score",
        value_label="Yes",
        pick_label="Both Teams To Score – YES",
    ),
]


def _parse_kickoff(fixture: Dict[str, Any]) -> Optional[datetime]:
    dt_str = (fixture.get("fixture") or {}).get("date")
    if not dt_str:
        return None
    try:
        # API-FOOTBALL format: 2025-11-17T20:00:00+00:00 ili sa 'Z'
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _build_odds_index(odds_list: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    index: Dict[int, List[Dict[str, Any]]] = {}
    for row in odds_list or []:
        fid = row.get("fixture_id")
        if fid is None:
            continue
        index.setdefault(fid, []).append(row)
    return index


def _get_market_odds(
    odds_index: Dict[int, List[Dict[str, Any]]],
    fixture_id: int,
    bet_name: str,
    value_label: str,
) -> Optional[float]:
    """
    Pronalazi kvotu za zadati market u clean-ovanim odds podacima:
    • bet_name npr. "Goals Over/Under"
    • value_label npr. "Over 2.5"
    Uzimamo 'najnižu' kvotu (konzervativno) među bookmaker-ima.
    """
    rows = odds_index.get(fixture_id) or []
    found: List[float] = []
    for r in rows:
        if r.get("bet_name") == bet_name and r.get("label") == value_label:
            odd_val = r.get("odd")
            try:
                if odd_val is not None:
                    found.append(float(odd_val))
            except (TypeError, ValueError):
                continue
    if not found:
        return None
    return min(found)


def _build_candidate_legs(
    fixtures: List[Dict[str, Any]],
    odds_list: List[Dict[str, Any]],
    markets: List[MarketConfig] | None = None,
    max_legs_per_market: int = 150,
) -> List[Dict[str, Any]]:
    """
    Iz fixtures + odds generiše legs za sve definisane markete.
    Svaki leg je dict sa ključevima:
      fixture_id, league_id, league_name, league_country,
      home, away, kickoff, market, family, pick, odds
    """
    if markets is None:
        markets = MARKETS

    odds_index = _build_odds_index(odds_list)
    legs: List[Dict[str, Any]] = []

    for fx in fixtures or []:
        league = fx.get("league") or {}
        lid = league.get("id")
        if lid is None or lid not in ALLOW_SET:
            continue

        fixture_info = fx.get("fixture") or {}
        fixture_id = fixture_info.get("id")
        if fixture_id is None:
            continue

        # status mora biti not-started
        status = (fixture_info.get("status") or {}).get("short")
        if status not in (None, "NS", "TBD"):
            # već u toku ili završena utakmica
            continue

        kickoff = _parse_kickoff(fx)
        if kickoff is None:
            continue

        teams = fx.get("teams") or {}
        home_team = (teams.get("home") or {}).get("name")
        away_team = (teams.get("away") or {}).get("name")
        if not home_team or not away_team:
            continue

        for mc in markets:
            odd_val = _get_market_odds(odds_index, fixture_id, mc.bet_name, mc.value_label)
            if odd_val is None:
                continue

            leg = {
                "fixture_id": fixture_id,
                "league_id": lid,
                "league_name": league.get("name"),
                "league_country": league.get("country"),
                "home": home_team,
                "away": away_team,
                "kickoff": fixture_info.get("date"),
                "market": mc.code,
                "family": mc.family,
                "pick": mc.pick_label,
                "odds": float(odd_val),
            }
            legs.append(leg)

    # limit per market
    by_market: Dict[str, List[Dict[str, Any]]] = {}
    for leg in legs:
        by_market.setdefault(leg["market"], []).append(leg)

    trimmed: List[Dict[str, Any]] = []
    for m_code, lst in by_market.items():
        # Sortiramo po kvoti opadajuće (veća kvota na vrhu)
        lst_sorted = sorted(lst, key=lambda x: x["odds"], reverse=True)
        trimmed.extend(lst_sorted[:max_legs_per_market])

    return trimmed


def _compute_total_odds(legs: List[Dict[str, Any]]) -> float:
    total = 1.0
    for leg in legs:
        total *= float(leg["odds"])
    return total


def _is_valid_ticket(
    legs: List[Dict[str, Any]],
    target_min: float,
    target_max: float,
    max_family_per_ticket: int,
) -> bool:
    if not legs:
        return False

    # Unique fixtures
    fixture_ids = {leg["fixture_id"] for leg in legs}
    if len(fixture_ids) != len(legs):
        return False

    # Family constraint
    family_counts: Dict[str, int] = {}
    for leg in legs:
        fam = leg.get("family") or "GEN"
        family_counts[fam] = family_counts.get(fam, 0) + 1
        if family_counts[fam] > max_family_per_ticket:
            return False

    total_odds = _compute_total_odds(legs)
    if total_odds < target_min or total_odds > target_max:
        return False

    return True


def mix_tickets(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    *,
    target_min: float = TARGET_ODDS_MIN_DEFAULT,
    target_max: float = TARGET_ODDS_MAX_DEFAULT,
    legs_min: int = LEGS_MIN_DEFAULT,
    legs_max: int = LEGS_MAX_DEFAULT,
    max_combos: int = 80,
    max_tickets: int = 3,
    max_family_per_ticket: int = MAX_FAMILY_PER_TICKET_DEFAULT,
) -> Dict[str, Any]:
    """
    Glavni LAYER 2 mixer:

    1) Iz fixtures + odds gradi kandidat legs za nekoliko tržišta (O15, O25, HT_O05, U35, HOME, BTTS_YES).
    2) Nasumično kombinuje legs u tikete sa:
       - ukupna kvota u [target_min, target_max]
       - legs_min–legs_max utakmica
       - max 2 puta isti market family po tiketu
       - bez duplih fixture-a u tiketu
    3) Vraća dict:
       {
         "tickets": [ {ticket_id, total_odds, legs:[...]} ],
         "meta": {...}
       }
    """
    candidates = _build_candidate_legs(fixtures, odds)
    random.shuffle(candidates)

    tickets: List[Dict[str, Any]] = []
    seen_signatures: Set[Tuple[Tuple[int, str], ...]] = set()

    attempts = 0
    max_attempts = max_combos * 10

    while len(tickets) < max_tickets and attempts < max_attempts:
        attempts += 1
        if len(candidates) < legs_min:
            break

        k = random.randint(legs_min, min(legs_max, len(candidates)))
        sample = random.sample(candidates, k=k)

        if not _is_valid_ticket(sample, target_min, target_max, max_family_per_ticket):
            continue

        sig = tuple(sorted((leg["fixture_id"], leg["market"]) for leg in sample))
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        total_odds = _compute_total_odds(sample)
        ticket = {
            "ticket_id": f"MIX-{len(tickets) + 1}",
            "total_odds": round(total_odds, 2),
            "legs": sorted(sample, key=lambda x: x["kickoff"] or ""),
        }
        tickets.append(ticket)

    return {
        "tickets": tickets,
        "meta": {
            "candidates_total": len(candidates),
            "attempts": attempts,
            "target_min": target_min,
            "target_max": target_max,
            "legs_min": legs_min,
            "legs_max": legs_max,
        },
    }
