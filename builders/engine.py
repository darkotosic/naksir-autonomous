# builders/engine.py
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Dict, List, Tuple, Set, Optional

from .registry import get_builder

###############################################################################
# League priority (EU TOP ligе i takmičenja)
###############################################################################

EURO_PRIORITY: Dict[int, int] = {
    # Big 5 ligе
    39: 100,   # England - Premier League
    140: 95,   # Spain - La Liga
    135: 95,   # Italy - Serie A
    78: 90,    # Germany - Bundesliga
    61: 85,    # France - Ligue 1

    # Evropska takmičenja
    2: 120,    # UEFA Champions League
    3: 115,    # UEFA Europa League
    848: 110,  # UEFA Conference League
    5: 105,    # UEFA Nations League

    # Jake dodatne ligе
    88: 80,    # Netherlands - Eredivisie
    94: 75,    # Portugal - Primeira Liga
    203: 70,   # Turkey - Super Lig
    71: 70,    # Belgium - Pro League
    566: 65,   # Serbia - SuperLiga
}


def league_priority_from_leg(leg: Dict[str, Any]) -> int:
    try:
        lid = int(leg.get("league_id", 0))
    except Exception:
        return 1
    return EURO_PRIORITY.get(lid, 1)


###############################################################################
# Helper functions
###############################################################################


def _compute_total_odds(legs: List[Dict[str, Any]]) -> float:
    """
    Multiplikativni akumulator za decimalne kvote.
    Očekuje leg["odds"] kao float-abilan.
    """
    total = 1.0
    for leg in legs:
        try:
            total *= float(leg["odds"])
        except (KeyError, TypeError, ValueError):
            return 0.0
    return round(total, 4)


def _get_leg_score(leg: Dict[str, Any]) -> float:
    """
    Normalizovan "quality" score za jedan leg.
    Podržani ključеvi:
      - model_score: 0–100
      - confidence: 0–100
      - score: 0–100
    Fallback = 0.0.
    """
    for key in ("model_score", "confidence", "score"):
        val = leg.get(key)
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(val)
        except Exception:
            continue
    return 0.0


def _group_legs_by_fixture(legs: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Utility za debug/analitiku – nije obavezan za mixer, ali koristan.
    """
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for leg in legs:
        fid = int(leg.get("fixture_id", 0))
        grouped.setdefault(fid, []).append(leg)
    return grouped


###############################################################################
# Ticket validation & mixing
###############################################################################


def _is_valid_ticket(
    legs: List[Dict[str, Any]],
    target_min: float,
    target_max: float,
    max_family_per_ticket: int,
) -> bool:
    """
    Validacija tiketa:
      - ne sme biti prazan
      - nema duplih fixture-a
      - limit na market_family (samo ako leg ima market_family)
      - ukupna kvota u [target_min, target_max]
    """
    if not legs:
        return False

    # 1) Nema duplih fixture-a.
    fixture_ids = [int(leg["fixture_id"]) for leg in legs if "fixture_id" in leg]
    if len(fixture_ids) != len(set(fixture_ids)):
        return False

    # 2) Market family limit – primeni samo ako builder popunjava "market_family".
    if max_family_per_ticket > 0:
        family_counts: Dict[str, int] = {}
        for leg in legs:
            fam = leg.get("market_family")
            if not fam:
                continue
            fam = str(fam)
            family_counts[fam] = family_counts.get(fam, 0) + 1
            if family_counts[fam] > max_family_per_ticket:
                return False

    # 3) Ukupna kvota.
    total_odds = _compute_total_odds(legs)
    if total_odds <= 0.0:
        return False
    if total_odds < target_min or total_odds > target_max:
        return False

    return True


def _build_candidate_ticket(
    pool: List[Dict[str, Any]],
    desired_legs: int,
    target_min: float,
    target_max: float,
    max_family_per_ticket: int,
    used_fixtures: Set[int],
) -> Optional[List[Dict[str, Any]]]:
    """
    Greedy konstruktor jednog tiketa:
      - startuje od najkvalitetnijih legova (score + EU priority)
      - poštuje:
          * unique fixture unutar seta
          * market_family limit po tiketu
      - cilja tačno desired_legs
      - konačna kvota mora biti u [target_min, target_max]
    """
    # Sortiramo pool:
    # 1) league priority (desc)
    # 2) leg score (desc)
    # 3) kickoff (asc) ako postoji
    def _sort_key(leg: Dict[str, Any]) -> Tuple[int, float, str]:
        prio = league_priority_from_leg(leg)
        score = _get_leg_score(leg)
        kickoff = str(leg.get("kickoff") or "")
        return (prio, score, kickoff)

    sorted_pool = sorted(pool, key=_sort_key, reverse=True)

    ticket_legs: List[Dict[str, Any]] = []
    ticket_fixture_ids: Set[int] = set()
    family_counts: Dict[str, int] = {}

    for leg in sorted_pool:
        if len(ticket_legs) >= desired_legs:
            break

        try:
            fid = int(leg["fixture_id"])
        except Exception:
            continue

        # Ne koristimo fixture koji je već u nekom tiketu ovog seta.
        if fid in used_fixtures:
            continue

        # Ne dupliramo fixture unutar istog tiketa.
        if fid in ticket_fixture_ids:
            continue

        # Market family limit unutar tiketa.
        fam = leg.get("market_family")
        if fam and max_family_per_ticket > 0:
            fam = str(fam)
            current = family_counts.get(fam, 0)
            if current + 1 > max_family_per_ticket:
                continue

        ticket_legs.append(leg)
        ticket_fixture_ids.add(fid)
        if fam:
            family_counts[fam] = family_counts.get(fam, 0) + 1

    if len(ticket_legs) != desired_legs:
        return None

    if not _is_valid_ticket(ticket_legs, target_min, target_max, max_family_per_ticket):
        return None

    return ticket_legs


def _mix_legs_into_tickets(
    legs: List[Dict[str, Any]],
    *,
    target_min: float,
    target_max: float,
    legs_min: int,
    legs_max: int,
    max_family_per_ticket: int,
    max_tickets: int,
) -> List[Dict[str, Any]]:
    """
    Core mixer za jedan ticket set.

    Strategija:
      1) Čistimo legs (validne kvote).
      2) Pokušavamo da pravimo tikete sa legs_max nogu.
      3) Ako nema dovoljno → fallback na legs_max-1, ..., legs_min.
      4) Fixture se ne ponavlja unutar istog seta (hard rule).
    """
    if legs_min < 1:
        legs_min = 1
    if legs_max < legs_min:
        legs_max = legs_min
    if max_tickets < 1:
        return []

    # Filter legs bez validnih kvota.
    clean_legs: List[Dict[str, Any]] = []
    for leg in legs:
        try:
            o = float(leg["odds"])
            if o <= 1.0:
                continue
        except Exception:
            continue
        clean_legs.append(leg)

    if not clean_legs:
        print("[DBG] Mixer: no valid legs after cleaning.")
        return []

    used_fixtures: Set[int] = set()
    tickets: List[Dict[str, Any]] = []

    for desired_legs in range(legs_max, legs_min - 1, -1):
        if len(tickets) >= max_tickets:
            break

        attempts = 0
        max_attempts = len(clean_legs) * 3

        while len(tickets) < max_tickets and attempts < max_attempts:
            attempts += 1

            ticket_legs = _build_candidate_ticket(
                pool=clean_legs,
                desired_legs=desired_legs,
                target_min=target_min,
                target_max=target_max,
                max_family_per_ticket=max_family_per_ticket,
                used_fixtures=used_fixtures,
            )

            if not ticket_legs:
                break

            for leg in ticket_legs:
                try:
                    used_fixtures.add(int(leg["fixture_id"]))
                except Exception:
                    continue

            # Osnovni AI score = prosečni leg score.
            base_ai = 0.0
            if ticket_legs:
                base_ai = sum(_get_leg_score(l) for l in ticket_legs) / len(ticket_legs)

            # BOOST za premium lige: svaka noga dodaje (league_priority * 0.01).
            boost = sum(league_priority_from_leg(l) for l in ticket_legs) * 0.01
            ai_score = round(base_ai + boost, 2)

            tickets.append(
                {
                    "legs": ticket_legs,
                    "total_odds": _compute_total_odds(ticket_legs),
                    "ai_score": ai_score,
                }
            )

        print(
            f"[DBG] Mixer: desired_legs={desired_legs}, attempts={attempts}, "
            f"tickets_now={len(tickets)}"
        )

    tickets.sort(
        key=lambda t: (
            float(t.get("ai_score", 0.0)),
            float(t.get("total_odds", 0.0)),
        ),
        reverse=True,
    )
    return tickets


###############################################################################
# Builders orchestration
###############################################################################


def _build_legs_for_builders(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    builder_codes: List[str],
    max_legs_per_builder: int = 200,
) -> List[Dict[str, Any]]:
    """
    Poziva listu buildera i vraća deduplikovan pool legs.

    Po builderu:
      - cap na max_legs_per_builder
      - deduplikacija po (fixture_id, market)
    Na kraju:
      - globalni sort po EU priority + kickoff + score
      - preferira top evropske lige pre ostalih.
    """
    pool: List[Dict[str, Any]] = []
    seen: Set[Tuple[int, str]] = set()

    print(f"[DBG] === Builder group start: {builder_codes} ===")

    for code in builder_codes:
        builder = get_builder(code)
        if builder is None:
            print(f"[WARN] Builder not found: {code}")
            continue

        try:
            legs = builder(fixtures=fixtures, odds=odds, max_legs=max_legs_per_builder)
        except TypeError:
            legs = builder(fixtures=fixtures, odds=odds)  # type: ignore[call-arg]
        except Exception as exc:
            print(f"[ERR] Builder {code} raised exception: {exc}")
            continue

        if not legs:
            print(f"[DBG] Builder {code} → returned 0 legs")
            continue

        print(f"[DBG] Builder {code} → raw legs: {len(legs)}")

        for leg in legs[:max_legs_per_builder]:
            try:
                fid = int(leg["fixture_id"])
                market = str(leg.get("market") or "")
            except Exception:
                continue

            key = (fid, market)
            if key in seen:
                continue

            seen.add(key)
            pool.append(leg)

    if not pool:
        print("[DBG] === Builder group done → pool size: 0 ===")
        return []

    # Globalni sort: prvo EU priority, pa leg score, pa kickoff.
    def _pool_key(leg: Dict[str, Any]) -> Tuple[int, float, str]:
        prio = league_priority_from_leg(leg)
        score = _get_leg_score(leg)
        kickoff = str(leg.get("kickoff") or "")
        return (prio, score, kickoff)

    pool.sort(key=_pool_key, reverse=True)

    print(f"[DBG] === Builder group done → pool size: {len(pool)} (sorted by EU priority) ===")
    return pool


###############################################################################
# High-level ticket set builder
###############################################################################


def _build_ticket_set_for_config(
    config: Dict[str, Any],
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build jednog logičkog tiketskog seta na osnovu config zapisa.

    Očekivani ključеvi u config:
      - code: str
      - label: str
      - description: str
      - builders: list[str]
      - target_min: float
      - target_max: float
      - legs_min: int
      - legs_max: int
      - max_family_per_ticket: int
      - max_tickets: int
      - min_leg_score: float (opciono)
    """
    code = config["code"]
    label = config.get("label", code)
    print(f"\n[DBG] === Build SET {code} ({label}) ===")

    builders = config["builders"]
    legs = _build_legs_for_builders(fixtures, odds, builders)

    print(f"[DBG] SET {code} → legs in pool before scoring filter: {len(legs)}")

    min_leg_score = float(config.get("min_leg_score", 0.0))
    if min_leg_score > 0.0:
        legs = [leg for leg in legs if _get_leg_score(leg) >= min_leg_score]
        print(f"[DBG] SET {code} → legs after score >= {min_leg_score}: {len(legs)}")

    if not legs:
        return {
            "code": code,
            "label": label,
            "description": config.get("description", ""),
            "status": "NO_LEGS",
            "tickets": [],
        }

    tickets = _mix_legs_into_tickets(
        legs,
        target_min=float(config["target_min"]),
        target_max=float(config["target_max"]),
        legs_min=int(config["legs_min"]),
        legs_max=int(config["legs_max"]),
        max_family_per_ticket=int(config.get("max_family_per_ticket", 2)),
        max_tickets=int(config.get("max_tickets", 3)),
    )

    if not tickets:
        print(f"[DBG] SET {code} → mixer produced 0 tickets")
        return {
            "code": code,
            "label": label,
            "description": config.get("description", ""),
            "status": "NO_TICKETS",
            "tickets": [],
        }

    out_tickets: List[Dict[str, Any]] = []
    for idx, t in enumerate(tickets, start=1):
        ticket_id = f"{code}-{idx}"
        out_tickets.append(
            {
                "id": ticket_id,
                "code": code,
                "label": label,
                "total_odds": float(t["total_odds"]),
                "ai_score": float(t.get("ai_score", 0.0)),
                "legs": t["legs"],
            }
        )

    print(f"[DBG] SET {code} DONE → final tickets: {len(out_tickets)}")
    return {
        "code": code,
        "label": label,
        "description": config.get("description", ""),
        "status": "OK",
        "tickets": out_tickets,
    }


###############################################################################
# Public entrypoint
###############################################################################


def build_all_ticket_sets(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    ticket_sets_config: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Glavni public API za engine.

    Vraća strukturu kompatibilnu sa frontendom i Telegram slojem:
    {
        "date": "YYYY-MM-DD",
        "generated_at": "ISO timestamp",
        "sets": [ ... ],
    }
    """
    today = date.today().isoformat()
    generated_at = datetime.utcnow().isoformat() + "Z"

    print(f"[DBG] === Engine start for {today} ===")
    print(f"[DBG] Fixtures in: {len(fixtures)}, odds in: {len(odds)}")
    print(f"[DBG] Ticket sets to build: {len(ticket_sets_config)}")

    sets_out: List[Dict[str, Any]] = []
    for cfg in ticket_sets_config:
        try:
            sets_out.append(_build_ticket_set_for_config(cfg, fixtures, odds))
        except Exception as exc:
            code = cfg.get("code", "UNNAMED")
            print(f"[ERR] Failed to build set {code}: {exc}")
            sets_out.append(
                {
                    "code": code,
                    "label": cfg.get("label", code),
                    "description": cfg.get("description", ""),
                    "status": "ERROR",
                    "tickets": [],
                }
            )

    total_tickets = sum(len(s["tickets"]) for s in sets_out)
    print(f"[DBG] === SUMMARY: {len(sets_out)} sets, {total_tickets} total tickets ===")

    return {
        "date": today,
        "generated_at": generated_at,
        "sets": sets_out,
    }


# Backwards kompatibilnost – globalni TICKET_SETS_CONFIG ako već postoji
try:
    TICKET_SETS_CONFIG  # type: ignore[name-defined]
except NameError:
    TICKET_SETS_CONFIG: List[Dict[str, Any]] = []


def build_ticket_sets(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Stari entrypoint – koristi globalni TICKET_SETS_CONFIG.
    """
    return build_all_ticket_sets(fixtures, odds, TICKET_SETS_CONFIG)
