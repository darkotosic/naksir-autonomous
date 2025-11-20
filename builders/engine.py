# builders/engine.py
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Dict, List, Tuple, Set

from .registry import get_builder


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

    # 1) svaki fixture max jednom u tiketu
    fixture_ids = {leg["fixture_id"] for leg in legs}
    if len(fixture_ids) != len(legs):
        return False

    # 2) ograničenje market_family u tiketu
    family_counts: Dict[str, int] = {}
    for leg in legs:
        fam = leg.get("market_family") or "GEN"
        family_counts[fam] = family_counts.get(fam, 0) + 1
        if family_counts[fam] > max_family_per_ticket:
            return False

    # 3) ukupna kvota u target range (2.00–3.00)
    total_odds = _compute_total_odds(legs)
    if total_odds < target_min or total_odds > target_max:
        return False

    return True


def _mix_legs_into_tickets(
    legs: List[Dict[str, Any]],
    *,
    target_min: float,
    target_max: float,
    legs_min: int,
    legs_max: int,
    max_tickets: int,
    max_attempts: int = 400,
    max_family_per_ticket: int = 2,
) -> List[Dict[str, Any]]:
    """
    Random mixer nad već izgrađenim legovima.

    Pravila:
      - pokušava da složi 3–5 legova (legs_min/legs_max)
      - ukupna kvota 2.00–3.00
      - max_family_per_ticket ograničava koliko puta ista family sme da se pojavi
      - nema duplikata po (fixture_id, market) kombinaciji
    """
    if not legs:
        return []

    tickets: List[Dict[str, Any]] = []
    seen_signatures: Set[Tuple[Tuple[int, str], ...]] = set()

    legs_shuffled = list(legs)
    random.shuffle(legs_shuffled)

    attempts = 0
    while len(tickets) < max_tickets and attempts < max_attempts:
        attempts += 1

        if len(legs_shuffled) < legs_min:
            break

        k = random.randint(legs_min, min(legs_max, len(legs_shuffled)))
        sample = random.sample(legs_shuffled, k=k)

        if not _is_valid_ticket(sample, target_min, target_max, max_family_per_ticket):
            continue

        sig = tuple(sorted((leg["fixture_id"], leg["market"]) for leg in sample))
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        total_odds = round(_compute_total_odds(sample), 2)
        ticket = {
            "total_odds": total_odds,
            "legs": sorted(sample, key=lambda x: x["kickoff"]),
        }
        tickets.append(ticket)

    return tickets


# 10 setova – svaki set druga filozofija
TICKET_SETS_CONFIG: List[Dict[str, Any]] = [
    # 1) Goals MIX: O1.5 + O2.5 + U3.5 (soft mix, max 2 iz iste family)
    {
        "code": "SET_GOALS_MIX",
        "label": "[GOALS MIX]",
        "builders": ["O15", "O25", "U35"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 2,
    },
    # 2) Čisti O1.5
    {
        "code": "SET_O15",
        "label": "[OVER 1.5]",
        "builders": ["O15"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
    # 3) Čisti O2.5
    {
        "code": "SET_O25",
        "label": "[OVER 2.5]",
        "builders": ["O25"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
    # 4) Čisti O3.5
    {
        "code": "SET_O35",
        "label": "[OVER 3.5]",
        "builders": ["O35"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
    # 5) UNDER 3.5
    {
        "code": "SET_UNDER",
        "label": "[UNDER 3.5]",
        "builders": ["U35"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
    # 6) HOME + DC miks (klasičan "sigurniji" set)
    {
        "code": "SET_HOME_DC",
        "label": "[HOME/DC MIX]",
        "builders": ["HOME", "DC_1X", "DC_X2"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 2,
    },
    # 7) AWAY + DRAW miks (kontra/value set)
    {
        "code": "SET_AWAY_DRAW",
        "label": "[AWAY/DRAW MIX]",
        "builders": ["AWAY", "DRAW"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 2,
    },
    # 8) BTTS YES
    {
        "code": "SET_BTTS_YES",
        "label": "[BTTS YES]",
        "builders": ["BTTS_YES"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
    # 9) BTTS NO
    {
        "code": "SET_BTTS_NO",
        "label": "[BTTS NO]",
        "builders": ["BTTS_NO"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
    # 10) HT Over 0.5 (prvo poluvreme)
    {
        "code": "SET_HT",
        "label": "[HT O0.5]",
        "builders": ["HT_O05"],
        "legs_min": 3,
        "legs_max": 5,
        "target_min": 2.0,
        "target_max": 3.0,
        "max_tickets": 3,
        "max_family_per_ticket": 3,
    },
]

    # ------------------------------------------------------------------
    # OPTIMIZATION PACK — NEW MIX SETS
    # ------------------------------------------------------------------
    {
        "code": "SET_MIX_O15_O25",
        "label": "[MIX] Over 1.5 + Over 2.5",
        "markets": ["O15", "O25"],
        "market_family": "GOALS",
        "legs_min": 2,
        "legs_max": 4,
        "min_total_odds": 2.00,
        "max_total_odds": 3.20,
        "max_tickets": 3,
        # max 2 puta isti market family po tiketu
        "max_family_per_ticket": 2,
    },
    {
        "code": "SET_MIX_U35_BTTS",
        "label": "[MIX] Under 3.5 + BTTS",
        "markets": ["U35", "BTTS_YES", "BTTS_NO"],
        "market_family": "MIX_U35_BTTS",
        "legs_min": 2,
        "legs_max": 4,
        "min_total_odds": 2.00,
        "max_total_odds": 3.50,
        "max_tickets": 3,
        # max 2 legs iz iste family (npr. da ne budu 3x BTTS)
        "max_family_per_ticket": 2,
    },
    {
        "code": "SET_MIX_HOME_DC",
        "label": "[MIX] Home Win + DC",
        "markets": ["HOME", "1X", "X2"],
        "market_family": "WIN_DC",
        "legs_min": 2,
        "legs_max": 4,
        "min_total_odds": 2.00,
        "max_total_odds": 3.00,
        "max_tickets": 3,
        # max 2 legs iz WIN/DC familije po tiketu
        "max_family_per_ticket": 2,
    },


def _build_legs_for_builders(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    builder_codes: List[str],
    max_legs_per_builder: int = 150,
) -> List[Dict[str, Any]]:
    """
    Pokreće više buildera i kombinuje njihove legove u jedan pool.
    Uklanja duplikate po (fixture_id, market).
    """
    pool: List[Dict[str, Any]] = []
    seen: Set[Tuple[int, str]] = set()

    for code in builder_codes:
        builder_fn = get_builder(code)
        legs = builder_fn(fixtures, odds, max_legs=max_legs_per_builder)
        for leg in legs:
            key = (leg["fixture_id"], leg["market"])
            if key in seen:
                continue
            seen.add(key)
            pool.append(leg)

    return pool


def _build_ticket_set_for_config(
    config: Dict[str, Any],
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
) -> Dict[str, Any]:
    builders = config["builders"]
    target_min = config["target_min"]
    target_max = config["target_max"]
    legs_min = config["legs_min"]
    legs_max = config["legs_max"]
    max_family_per_ticket = config["max_family_per_ticket"]

    legs = _build_legs_for_builders(fixtures, odds, builders)

    # primarni pokušaj: max_tickets (obično 3)
    tickets = _mix_legs_into_tickets(
        legs,
        target_min=target_min,
        target_max=target_max,
        legs_min=legs_min,
        legs_max=legs_max,
        max_tickets=config["max_tickets"],
        max_family_per_ticket=max_family_per_ticket,
    )

    status = "OK"
    effective_max_tickets = config["max_tickets"]

    if not tickets:
        # fallback: 2 tiketa
        effective_max_tickets = 2
        tickets = _mix_legs_into_tickets(
            legs,
            target_min=target_min,
            target_max=target_max,
            legs_min=legs_min,
            legs_max=legs_max,
            max_tickets=2,
            max_family_per_ticket=max_family_per_ticket,
        )
        if tickets:
            status = "FALLBACK_2"
        else:
            # fallback: 1 tiket
            effective_max_tickets = 1
            tickets = _mix_legs_into_tickets(
                legs,
                target_min=target_min,
                target_max=target_max,
                legs_min=legs_min,
                legs_max=legs_max,
                max_tickets=1,
                max_family_per_ticket=max_family_per_ticket,
            )
            if tickets:
                status = "FALLBACK_1"
            else:
                status = "NO_DATA"

    # dodaj ID-eve u tikete
    code = config["code"]
    final_tickets: List[Dict[str, Any]] = []
    for idx, t in enumerate(tickets, start=1):
        t_id = f"{code}-{idx}"
        final_tickets.append(
            {
                "ticket_id": t_id,
                "label": config["label"],
                "total_odds": t["total_odds"],
                "legs": t["legs"],
            }
        )

    return {
        "code": code,
        "label": config["label"],
        "status": status,
        "requested_max_tickets": config["max_tickets"],
        "effective_max_tickets": effective_max_tickets,
        "tickets": final_tickets,
        "legs_pool_size": len(legs),
    }


def build_all_ticket_sets(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Glavna funkcija LAYER 2:

    - prolazi kroz TICKET_SETS_CONFIG (10 setova)
    - za svaki set pokreće relevantne buildere
    - sklapa tikete 3→2→1 (fallback) sa target kvotom 2–3
    """
    today = date.today().isoformat()
    generated_at = datetime.utcnow().isoformat() + "Z"

    sets_out: List[Dict[str, Any]] = []

    for cfg in TICKET_SETS_CONFIG:
        set_result = _build_ticket_set_for_config(cfg, fixtures, odds)
        sets_out.append(set_result)

    return {
        "date": today,
        "generated_at": generated_at,
        "sets": sets_out,
    }
