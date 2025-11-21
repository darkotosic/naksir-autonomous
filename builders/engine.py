# builders/engine.py
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Dict, List, Tuple, Set, Optional

from .registry import get_builder

# ---------------------------------------------------------------------------
# Globalna konfiguracija setova tiketa (TICKET_SETS_CONFIG)
# ---------------------------------------------------------------------------
# Svaki "set" koristi grupu build-era i pravila:
#  - builders: šifre iz builders/registry.py (O15, O25, U35, BTTS_YES, HOME, DC_1X, ...)
#  - target_min/target_max: ukupna kvota po tiketu (npr. 2.0–3.0)
#  - legs_min/legs_max: broj utakmica u tiketu
#  - max_family_per_ticket: koliko puta ista market_family može da se pojavi u jednom tiketu
#  - max_tickets: maksimalan broj tiketa u tom setu

TICKET_SETS_CONFIG: List[Dict[str, Any]] = [
    # 1) Safe goals mix (O1.5 + O2.5 + U3.5)
    {
        "code": "S1_GOALS_MIX_SAFE",
        "label": "[S1] Safe Goals Mix 2+",
        "description": "Mix O1.5, O2.5 i U3.5 sa limitom na market family (max 2 po tiketu).",
        "builders": ["O15", "O25", "U35"],
        "target_min": 2.0,
        "target_max": 2.8,
        "legs_min": 3,
        "legs_max": 5,
        "max_family_per_ticket": 2,
        "max_tickets": 3,
        # min_leg_score ostavljamo na default 0.0, jer builderi trenutno ne pune model_score/confidence
    },

    # 2) Over 1.5 fokus (klasičan “sigurniji” goals tiket)
    {
        "code": "S2_OVER_15",
        "label": "[S2] Over 1.5 2+",
        "description": "Fokus na Over 1.5, više mečeva u tiketu.",
        "builders": ["O15"],
        "target_min": 2.0,
        "target_max": 3.0,
        "legs_min": 3,
        "legs_max": 6,
        "max_family_per_ticket": 3,  # goals family može i više puta, jer je ovo mono-goals tiket
        "max_tickets": 3,
    },

    # 3) Over 2.5 fokus
    {
        "code": "S3_OVER_25",
        "label": "[S3] Over 2.5 2+",
        "description": "Agresivniji goals tiket sa Over 2.5 marketom.",
        "builders": ["O25"],
        "target_min": 2.0,
        "target_max": 3.2,
        "legs_min": 2,
        "legs_max": 5,
        "max_family_per_ticket": 3,
        "max_tickets": 3,
    },

    # 4) BTTS fokus (YES/NO)
    {
        "code": "S4_BTTS",
        "label": "[S4] BTTS Focus 2+",
        "description": "BTTS YES/NO tiket, max 3 meča, čista BTTS family.",
        "builders": ["BTTS_YES", "BTTS_NO"],
        "target_min": 2.0,
        "target_max": 3.0,
        "legs_min": 2,
        "legs_max": 3,
        "max_family_per_ticket": 3,  # sve je BTTS family, nema smisla da gušimo
        "max_tickets": 3,
    },

    # 5) Rezultat + Double Chance (HOME, AWAY, 1X, X2)
    {
        "code": "S5_RESULT_DC",
        "label": "[S5] Result & DC 2+",
        "description": "Mix HOME/AWAY i DC (1X, X2) sa blagim limitom market family.",
        "builders": ["HOME", "AWAY", "DC_1X", "DC_X2"],
        "target_min": 2.0,
        "target_max": 3.0,
        "legs_min": 2,
        "legs_max": 4,
        "max_family_per_ticket": 2,
        "max_tickets": 3,
    },

    # 6) HT Over 0.5 – specijal za prvo poluvreme
    {
        "code": "S6_HT_OVER_05",
        "label": "[S6] HT Over 0.5 2+",
        "description": "Prvo poluvreme goals (HT Over 0.5), do 5 mečeva u tiketu.",
        "builders": ["HT_O05"],
        "target_min": 2.0,
        "target_max": 3.0,
        "legs_min": 3,
        "legs_max": 5,
        "max_family_per_ticket": 3,
        "max_tickets": 3,
    },
]


###############################################################################
# Helper functions
###############################################################################


def _compute_total_odds(legs: List[Dict[str, Any]]) -> float:
    """
    Multiplicative accumulator for decimal odds.
    Expects each leg["odds"] to be castable to float.
    """
    total = 1.0
    for leg in legs:
        try:
            total *= float(leg["odds"])
        except (KeyError, TypeError, ValueError):
            # If odds are missing or invalid, treat as fatal for this ticket.
            return 0.0
    return round(total, 4)


def _get_leg_score(leg: Dict[str, Any]) -> float:
    """
    Normalized "quality" score for a leg.
    Builders are free to attach any of:
      - model_score: 0–100
      - confidence: 0–100
    Fallback is 0.0 (lowest priority).
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
    Utility primarily for debugging / analytics.
    Not strictly required by mixer logic but handy to have.
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
    Applies all ticket-level constraints:
      - non-empty
      - no duplicate fixtures
      - market family cap (only for legs that actually define market_family)
      - total odds in [target_min, target_max]
    """
    if not legs:
        return False

    # 1) No duplicate fixtures inside a single ticket.
    fixture_ids = [int(leg["fixture_id"]) for leg in legs if "fixture_id" in leg]
    if len(fixture_ids) != len(set(fixture_ids)):
        return False

    # 2) Market family limit – enforced only if builder sets "market_family".
    #    Ovo sprečava da stari builderi bez market_family ubiju sve tikete.
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

    # 3) Odds range.
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
    Greedy builder:
      - start from highest-scoring legs
      - respect:
          * unique fixture rule
          * market-family per ticket cap
      - aim for exactly desired_legs per ticket
      - final odds must be in [target_min, target_max]
    Returns:
      - list of legs if valid ticket can be built
      - None if no valid combo found
    """
    # Sort once by descending score (stable – we don't mutate pool itself).
    sorted_pool = sorted(pool, key=_get_leg_score, reverse=True)

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

        # Do not reuse fixtures that are already in other tickets in this set.
        if fid in used_fixtures:
            continue

        # Do not duplicate fixture inside the same ticket.
        if fid in ticket_fixture_ids:
            continue

        # Market family rule within ticket.
        fam = leg.get("market_family")
        if fam and max_family_per_ticket > 0:
            fam = str(fam)
            current = family_counts.get(fam, 0)
            if current + 1 > max_family_per_ticket:
                continue

        # Temporarily add leg and check odds only when we have full size.
        ticket_legs.append(leg)
        ticket_fixture_ids.add(fid)
        if fam:
            family_counts[fam] = family_counts.get(fam, 0) + 1

    # Validate size & odds.
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
    Core mixer engine for one ticket set.

    Strategy:
      1) Filter & sort legs by score (desc).
      2) Try to build tickets with legs_max first.
      3) Ako nema dovoljno, fallback na legs_max-1, ..., legs_min.
      4) Legs se ne ponavljaju unutar istog seta (fixture unique per set).
    """
    # Defensive bounds.
    if legs_min < 1:
        legs_min = 1
    if legs_max < legs_min:
        legs_max = legs_min
    if max_tickets < 1:
        return []

    # Clean legs: remove ones bez odds.
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

    # Used fixtures across tickets in this set – hard rule: 1 fixture per set.
    used_fixtures: Set[int] = set()
    tickets: List[Dict[str, Any]] = []

    # Fallback legs flow: n = legs_max ... legs_min
    for desired_legs in range(legs_max, legs_min - 1, -1):
        if len(tickets) >= max_tickets:
            break

        attempts = 0
        # Hard cap on attempts per leg-size to avoid infinite loops.
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
                break  # nothing more we can build for this desired_legs

            # Register used fixtures to keep tickets disjoint by fixture.
            for leg in ticket_legs:
                try:
                    used_fixtures.add(int(leg["fixture_id"]))
                except Exception:
                    continue

            tickets.append(
                {
                    "legs": ticket_legs,
                    "total_odds": _compute_total_odds(ticket_legs),
                    "ai_score": round(
                        sum(_get_leg_score(l) for l in ticket_legs) / len(ticket_legs),
                        2,
                    ),
                }
            )

        print(
            f"[DBG] Mixer: desired_legs={desired_legs}, attempts={attempts}, "
            f"tickets_now={len(tickets)}"
        )

    # Final sort by AI score desc (then total_odds desc for stability).
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
    Executes a list of builders and returns a de-duplicated legs pool.

    Each builder returned legs list[dict]. We:
      - cap by max_legs_per_builder
      - deduplicate by (fixture_id, market) pair
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
            # Backward compatibility: some builders might not accept max_legs.
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

    print(f"[DBG] === Builder group done → pool size: {len(pool)} ===")
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
    Builds one logical ticket set based on configuration entry.

    Expected config keys:
      - code: str
      - label: str
      - description: str
      - builders: list[str]              # registry codes
      - target_min: float                # min total odds
      - target_max: float                # max total odds
      - legs_min: int
      - legs_max: int
      - max_family_per_ticket: int
      - max_tickets: int                 # how many tickets in this set
      - min_leg_score: float (optional)  # drop legs below this score
    """
    code = config["code"]
    label = config.get("label", code)
    print(f"\n[DBG] === Build SET {code} ({label}) ===")

    builders = config["builders"]
    legs = _build_legs_for_builders(fixtures, odds, builders)

    print(f"[DBG] SET {code} → legs in pool before scoring filter: {len(legs)}")

    # Optional global leg score filter.
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

    # Assign stable IDs and normalize fields.
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
    Main public API for the engine.

    Parameters:
      - fixtures: raw fixtures list (already cleaned / filtered upstream)
      - odds: raw odds list (already cleaned / filtered upstream)
      - ticket_sets_config: list of dict entries (see _build_ticket_set_for_config)

    Returns structure compatible with frontend & Telegram layers, e.g.:

    {
        "date": "2025-11-21",
        "generated_at": "2025-11-21T07:03:12Z",
        "sets": [
            {
                "code": "SETGOALSMIX",
                "label": "GOALS MIX",
                "status": "OK",
                "tickets": [
                    {
                        "id": "SETGOALSMIX-1",
                        "total_odds": 2.31,
                        "ai_score": 77.3,
                        "legs": [ ... ],
                    },
                    ...
                ],
            },
            ...
        ],
    }
    """
    today = date.today().isoformat()
    generated_at = datetime.utcnow().isoformat()

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


# Backwards compatibility layer
# ------------------------------
# U postojećem kodu se najverovatnije koristi build_ticket_sets(fixtures, odds)
# i globalni TICKET_SETS_CONFIG definisan u ovom modu.
# Ovaj deo omogućava da engine radi i u staroj i u novoj šemi.

try:
    TICKET_SETS_CONFIG  # type: ignore[name-defined]
except NameError:
    # Ako nema konfiguracije, ostavi prazno – skripta neće pucati,
    # samo neće biti izgrađen nijedan set dok se ne definiše konfiguracija.
    TICKET_SETS_CONFIG: List[Dict[str, Any]] = []


def build_ticket_sets(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Stari naziv entrypoint funkcije – sada samo prosleđuje na build_all_ticket_sets
    koristeći globalni TICKET_SETS_CONFIG.
    """
    return build_all_ticket_sets(fixtures, odds, TICKET_SETS_CONFIG)
