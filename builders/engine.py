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

    # fixture duplikati
    fixture_ids = {leg["fixture_id"] for leg in legs}
    if len(fixture_ids) != len(legs):
        return False

    # family limit
    family_counts: Dict[str, int] = {}
    for leg in legs:
        fam = leg.get("market_family") or "GEN"
        family_counts[fam] = family_counts.get(fam, 0) + 1
        if family_counts[fam] > max_family_per_ticket:
            return False

    # kvota u range
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

    print(f"[DBG] Mixer start → available legs: {len(legs)} | target_min={target_min} target_max={target_max}")

    if not legs:
        print("[DBG] Mixer aborted → no legs")
        return []

    tickets: List[Dict[str, Any]] = []
    seen_signatures: Set[Tuple[Tuple[int, str], ...]] = set()

    legs_shuffled = list(legs)
    random.shuffle(legs_shuffled)

    attempts = 0
    while len(tickets) < max_tickets and attempts < max_attempts:
        attempts += 1

        k = random.randint(legs_min, min(legs_max, len(legs_shuffled)))
        sample = random.sample(legs_shuffled, k=k)

        if not _is_valid_ticket(sample, target_min, target_max, max_family_per_ticket):
            continue

        sig = tuple(sorted((leg["fixture_id"], leg["market"]) for leg in sample))
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)

        total_odds = round(_compute_total_odds(sample), 2)
        tickets.append({
            "total_odds": total_odds,
            "legs": sorted(sample, key=lambda x: x["kickoff"]),
        })

    print(f"[DBG] Mixer done → attempts={attempts}, tickets_created={len(tickets)}")
    return tickets


# TICKET_SETS_CONFIG (bez izmena, samo konfiguracija)
# ...

def _build_legs_for_builders(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    builder_codes: List[str],
    max_legs_per_builder: int = 150,
) -> List[Dict[str, Any]]:

    pool: List[Dict[str, Any]] = []
    seen: Set[Tuple[int, str]] = set()

    print(f"[DBG] === Builder group start: {builder_codes} ===")

    for code in builder_codes:
        builder_fn = get_builder(code)
        legs = builder_fn(fixtures, odds, max_legs=max_legs_per_builder)

        print(f"[DBG] Builder {code} → raw legs: {len(legs)}")

        for leg in legs:
            key = (leg["fixture_id"], leg["market"])
            if key in seen:
                continue
            seen.add(key)
            pool.append(leg)

    print(f"[DBG] Combined builder pool → {len(pool)} unique legs")
    return pool


def _build_ticket_set_for_config(
    config: Dict[str, Any],
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
) -> Dict[str, Any]:

    code = config["code"]
    print(f"\n[DBG] === Build SET {code} ===")

    builders = config["builders"]
    legs = _build_legs_for_builders(fixtures, odds, builders)

    print(f"[DBG] SET {code} → legs in pool: {len(legs)}")

    tickets = _mix_legs_into_tickets(
        legs,
        target_min=config["target_min"],
        target_max=config["target_max"],
        legs_min=config["legs_min"],
        legs_max=config["legs_max"],
        max_tickets=config["max_tickets"],
        max_family_per_ticket=config["max_family_per_ticket"],
    )

    status = "OK"
    effective_max_tickets = config["max_tickets"]

    print(f"[DBG] SET {code} → primary tickets: {len(tickets)}")

    if not tickets:
        print(f"[DBG] SET {code} → fallback to 2 tickets")
        tickets = _mix_legs_into_tickets(
            legs,
            target_min=config["target_min"],
            target_max=config["target_max"],
            legs_min=config["legs_min"],
            legs_max=config["legs_max"],
            max_tickets=2,
            max_family_per_ticket=config["max_family_per_ticket"],
        )
        if tickets:
            status = "FALLBACK_2"
            effective_max_tickets = 2
        else:
            print(f"[DBG] SET {code} → fallback to 1 ticket")
            tickets = _mix_legs_into_tickets(
                legs,
                target_min=config["target_min"],
                target_max=config["target_max"],
                legs_min=config["legs_min"],
                legs_max=config["legs_max"],
                max_tickets=1,
                max_family_per_ticket=config["max_family_per_ticket"],
            )
            if tickets:
                status = "FALLBACK_1"
                effective_max_tickets = 1
            else:
                print(f"[DBG] SET {code} → NO_DATA")
                status = "NO_DATA"
                effective_max_tickets = 0

    final_tickets = []
    for idx, t in enumerate(tickets, start=1):
        print(f"[DBG] Ticket {code}-{idx} → legs={len(t['legs'])}, total_odds={t['total_odds']}")
        final_tickets.append({
            "ticket_id": f"{code}-{idx}",
            "label": config["label"],
            "total_odds": t["total_odds"],
            "legs": t["legs"],
        })

    print(f"[DBG] SET {code} DONE → final tickets: {len(final_tickets)} (status={status})")

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

    print("\n\n[DBG] ========== BUILD ALL TICKET SETS ==========")
    today = date.today().isoformat()
    generated_at = datetime.utcnow().isoformat() + "Z"

    sets_out: List[Dict[str, Any]] = []

    for cfg in TICKET_SETS_CONFIG:
        sets_out.append(_build_ticket_set_for_config(cfg, fixtures, odds))

    total_tickets = sum(len(s["tickets"]) for s in sets_out)
    print(f"[DBG] === SUMMARY: {len(sets_out)} sets, {total_tickets} total tickets ===")

    return {
        "date": today,
        "generated_at": generated_at,
        "sets": sets_out,
    }
