# core_data/ticket_sets.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from math import prod

@dataclass
class Leg:
    fixture_id: int
    league_id: int
    pick: str          # npr. "O15", "U35", "BTTS_YES"
    family: str        # "GOALS_O", "GOALS_U", "BTTS", "HT_GOALS", "RESULT"
    odds: float
    confidence: float  # 0.0–1.0 ili već normalizovano
    tags: Tuple[str, ...] = ()

@dataclass
class Ticket:
    set_key: str
    ticket_key: str
    legs: List[Leg]

    @property
    def total_odds(self) -> float:
        if not self.legs:
            return 0.0
        return prod(l.odds for l in self.legs)


# ---------------------------------------------------------------------------
# Konfiguracije setova
# ---------------------------------------------------------------------------

SET_CONFIGS: List[Dict[str, Any]] = [
    {
        "key": "SET1_SAFE_GOALS_MIX",
        "tickets": [
            {
                "ticket_key": "S1_T1",
                "families": ["GOALS_U", "GOALS_O", "BTTS"],
                "legs_min": 3,
                "legs_max": 5,
                "max_per_family": 2,
            },
            {
                "ticket_key": "S1_T2",
                "families": ["GOALS_U", "GOALS_O"],
                "legs_min": 3,
                "legs_max": 4,
                "max_per_family": 2,
            },
            {
                "ticket_key": "S1_T3",
                "families": ["GOALS_O", "BTTS"],
                "legs_min": 2,
                "legs_max": 4,
                "max_per_family": 2,
            },
        ],
    },
    {
        "key": "SET2_HT_PRESSURE",
        "tickets": [
            {
                "ticket_key": "S2_T1",
                "families": ["HT_GOALS", "HT_DC"],
                "legs_min": 2,
                "legs_max": 4,
                "max_per_family": 2,
            },
            {
                "ticket_key": "S2_T2",
                "families": ["HT_GOALS"],
                "legs_min": 2,
                "legs_max": 3,
                "max_per_family": 3,
            },
            {
                "ticket_key": "S2_T3",
                "families": ["HT_GOALS", "HT_DC"],
                "legs_min": 2,
                "legs_max": 3,
                "max_per_family": 2,
            },
        ],
    },
    {
        "key": "SET3_BTTS_FOCUS",
        "tickets": [
            {
                "ticket_key": "S3_T1",
                "families": ["BTTS", "GOALS_O"],
                "legs_min": 2,
                "legs_max": 3,
                "max_per_family": 2,
            },
            {
                "ticket_key": "S3_T2",
                "families": ["BTTS"],
                "legs_min": 2,
                "legs_max": 3,
                "max_per_family": 3,
            },
            {
                "ticket_key": "S3_T3",
                "families": ["BTTS", "GOALS_O"],
                "legs_min": 2,
                "legs_max": 3,
                "max_per_family": 2,
            },
        ],
    },
    # ... nastavi isto do SET10 ...
    # Ovde možeš da dodaš još 7 configa po patternu gore,
    # sa različitim families, legs_min/max itd.
]


# ---------------------------------------------------------------------------
# Helperi
# ---------------------------------------------------------------------------

def _filter_candidates(
    candidates: List[Leg],
    families: List[str],
    min_conf: float = 0.62,
    min_odds: float = 1.10,
    max_odds: float = 1.40,
) -> List[Leg]:
    out: List[Leg] = []
    for leg in candidates:
        if leg.family not in families:
            continue
        if leg.odds < min_odds or leg.odds > max_odds:
            continue
        if leg.confidence < min_conf:
            continue
        out.append(leg)
    # sort by confidence desc
    out.sort(key=lambda x: x.confidence, reverse=True)
    return out


def _build_single_ticket(
    set_key: str,
    ticket_cfg: Dict[str, Any],
    pool: List[Leg],
    target_total_odds: float = 2.0,
) -> Optional[Ticket]:
    """
    Pokušava da izgradi jedan tiket iz pool-a.
    Poštuje:
      - families filter
      - legs_min / legs_max
      - max_per_family
      - 1 leg po fixture-u
      - ukupna kvota >= target_total_odds
    """
    families = ticket_cfg["families"]
    legs_min = ticket_cfg["legs_min"]
    legs_max = ticket_cfg["legs_max"]
    max_per_family = ticket_cfg.get("max_per_family", 99)

    candidates = _filter_candidates(pool, families=families)

    legs: List[Leg] = []
    family_count: Dict[str, int] = {}
    used_fixtures: set[int] = set()

    for leg in candidates:
        if len(legs) >= legs_max:
            break

        if leg.fixture_id in used_fixtures:
            continue

        fc = family_count.get(leg.family, 0)
        if fc >= max_per_family:
            continue

        legs.append(leg)
        used_fixtures.add(leg.fixture_id)
        family_count[leg.family] = fc + 1

        # ako smo došli do min broja legova i kvota je već 2+, možemo stati
        total_odds = prod(l.odds for l in legs)
        if len(legs) >= legs_min and total_odds >= target_total_odds:
            break

    if len(legs) < legs_min:
        return None

    ticket = Ticket(
        set_key=set_key,
        ticket_key=ticket_cfg["ticket_key"],
        legs=legs,
    )
    if ticket.total_odds < target_total_odds:
        # fallback – ako kvota i dalje nije 2+, tiket se odbacuje
        return None

    return ticket


def build_ticket_set(
    set_cfg: Dict[str, Any],
    candidates: List[Leg],
    target_total_odds: float = 2.0,
) -> List[Ticket]:
    """
    Gradi do 3 tiketa za jedan set, sa fallback logikom:
    - pokušaj do 3
    - ako ih ima <3 ali >=2 → vrati 2
    - ako <2 ali >=1 → vrati 1
    - ako 0 → [] (set se preskače)
    """
    set_key = set_cfg["key"]
    built: List[Ticket] = []

    for ticket_cfg in set_cfg["tickets"]:
        t = _build_single_ticket(set_key, ticket_cfg, candidates, target_total_odds)
        if t:
            built.append(t)

    # Fallback: smanji broj ako ih je više od 3 (teoretski)
    built = built[:3]

    if len(built) >= 3:
        return built
    if len(built) == 2:
        return built
    if len(built) == 1:
        return built

    return []


def build_all_sets(
    candidates: List[Leg],
    target_total_odds: float = 2.0,
) -> Dict[str, List[Ticket]]:
    """
    Glavna funkcija:
    - prolazi kroz svih 10 setova
    - za svaki pokušava da napravi 3/2/1 tiketa
    - vraća dict: {set_key: [tickets...]}
    """
    result: Dict[str, List[Ticket]] = {}

    for set_cfg in SET_CONFIGS:
        tickets = build_ticket_set(set_cfg, candidates, target_total_odds)
        if tickets:
            result[set_cfg["key"]] = tickets

    return result
