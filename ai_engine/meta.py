# ai_engine/meta.py
from __future__ import annotations

from typing import Any, Dict, List, Set

# Top / “trusted” lige (više verujemo uređenим takmičenjima)
TOP_LEAGUE_IDS: Set[int] = {
    39,   # England Premier League
    140,  # Spain La Liga
    135,  # Italy Serie A
    78,   # Germany Bundesliga
    61,   # France Ligue 1
    88,   # Netherlands Eredivisie
    203,  # Serbia SuperLiga
}

# Konzervativan raspon kvota po legu
SAFE_ODDS_MIN = 1.10
SAFE_ODDS_MAX = 1.40
OPTIMAL_ODDS_LOW = 1.15
OPTIMAL_ODDS_HIGH = 1.30


def _score_leg(leg: Dict[str, Any]) -> float:
    """
    Heuristički scoring jednog lega.

    - top lige + stabilne kvote = bonus
    - previše visoke kvote = penal
    - goals / BTTS family blago preferirani naspram čistog 1X2
    """
    score = 0.0

    league_id = leg.get("league_id")
    odds_raw = leg.get("odds", 0.0)
    try:
        odds = float(odds_raw or 0.0)
    except Exception:
        odds = 0.0

    market_family = str(leg.get("market_family") or leg.get("market") or "").upper()

    # 1) Liga
    if isinstance(league_id, int) and league_id in TOP_LEAGUE_IDS:
        score += 5.0
    else:
        score += 2.0

    # 2) Kvote – sweet spot 1.15–1.30
    if odds <= 1.01:
        score -= 4.0
    elif SAFE_ODDS_MIN <= odds <= SAFE_ODDS_MAX:
        score += 4.0
        if OPTIMAL_ODDS_LOW <= odds <= OPTIMAL_ODDS_HIGH:
            score += 3.0
        elif odds > OPTIMAL_ODDS_HIGH:
            score -= 1.0
    else:
        if odds < SAFE_ODDS_MIN:
            score -= 2.0
        else:
            score -= 5.0

    # 3) Market family
    if market_family in {"GOALS", "O/U"}:
        score += 1.5
    elif market_family in {"BTTS"}:
        score += 1.0
    elif market_family in {"1X2", "WIN"}:
        score += 0.5

    return score


def score_ticket(ticket: Dict[str, Any]) -> float:
    """
    Scoring celog tiketa na skali ~40–95.

    - kraći tiket (2–3 meča) = veći score
    - previše mečeva = penal
    - market diversity (mix goals/BTTS/DC/1X2) = plus
    - top lige / stabilne kvote po legu = glavni signal
    """
    legs = ticket.get("legs") or []
    if not isinstance(legs, list) or not legs:
        return 0.0

    base = 60.0

    leg_scores: List[float] = []
    for leg in legs:
        if not isinstance(leg, dict):
            continue
        try:
            leg_scores.append(_score_leg(leg))
        except Exception:
            continue

    if not leg_scores:
        return 40.0

    avg_leg_score = sum(leg_scores) / max(1, len(leg_scores))
    score = base + avg_leg_score

    n_legs = len(leg_scores)

    # dužina tiketa
    if n_legs == 1:
        score += 3.0
    elif n_legs == 2:
        score += 7.0
    elif n_legs == 3:
        score += 5.0
    elif n_legs == 4:
        score += 0.0
    elif n_legs == 5:
        score -= 4.0
    else:
        score -= 6.0

    # market diversity
    families = set(
        str(leg.get("market_family") or leg.get("market") or "").upper()
        for leg in legs
        if isinstance(leg, dict)
    )
    families.discard("")
    if len(families) >= 3:
        score += 5.0
    elif len(families) == 2:
        score += 3.0
    else:
        score -= 4.0

    # blaga korekcija po total odds
    total_odds_raw = ticket.get("total_odds", 0.0)
    try:
        total_odds = float(total_odds_raw or 0.0)
    except Exception:
        total_odds = 0.0

    if 2.0 <= total_odds <= 3.0:
        score += 2.0
    elif total_odds > 3.0:
        score -= 2.0

    # clamp
    if score < 40.0:
        score = 40.0
    if score > 95.0:
        score = 95.0

    return round(score, 1)


def annotate_ticket_sets_with_score(ticket_sets: Dict[str, Any]) -> Dict[str, Any]:
    """
    ticket_sets je dict oblika:
      {
        "sets": [
          {
            "code": "...",
            "label": "...",
            "tickets": [ { "legs": [...], ... }, ... ]
          },
          ...
        ]
      }

    Očisti loše tikete (ne-dict, bez legs) i svima ostalima dodaj "score".
    """
    sets = ticket_sets.get("sets") or []
    if not isinstance(sets, list):
        # ako je neko razbio strukturu, ne radimo ništa
        return ticket_sets

    new_sets: List[Dict[str, Any]] = []

    for s in sets:
        if not isinstance(s, dict):
            continue
        tickets = s.get("tickets") or []
        if not isinstance(tickets, list):
            continue

        clean_tickets: List[Dict[str, Any]] = []

        for t in tickets:
            if not isinstance(t, dict):
                continue
            legs = t.get("legs")
            if not isinstance(legs, list) or not legs:
                continue
            try:
                t["score"] = score_ticket(t)
                clean_tickets.append(t)
            except Exception:
                # bilo koji problem u scoringu → preskačemo tiket
                continue

        s["tickets"] = clean_tickets
        if clean_tickets:
            new_sets.append(s)

    ticket_sets["sets"] = new_sets
    return ticket_sets


def get_adaptive_min_score(fixtures_count: int, raw_total_tickets: int) -> float:
    """
    Dinamički prag za AI filter:

    - malo mečeva / malo tiketa → prag pada (ne ubijamo dan)
    - puno mečeva / puno tiketa → prag raste (biramo samo najbolje)
    """
    base = 62.0

    # 1) količina mečeva
    if fixtures_count <= 40:
        base -= 6.0
    elif fixtures_count <= 80:
        base -= 3.0
    elif fixtures_count >= 200:
        base += 3.0
    elif fixtures_count >= 120:
        base += 1.5

    # 2) broj kandidovanih tiketa
    if raw_total_tickets <= 3:
        base -= 4.0
    elif raw_total_tickets <= 6:
        base -= 2.0
    elif raw_total_tickets >= 15:
        base += 3.0
    elif raw_total_tickets >= 10:
        base += 1.5

    if base < 52.0:
        base = 52.0
    if base > 75.0:
        base = 75.0

    return base
