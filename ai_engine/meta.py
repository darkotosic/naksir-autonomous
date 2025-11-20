# ai_engine/meta.py
from __future__ import annotations

from typing import Any, Dict, List

# Top / “trusted” lige (tipsterska fora – više verujemo uređenim ligama)
TOP_LEAGUE_IDS = {
    39,   # England Premier League
    140,  # Spain La Liga
    135,  # Italy Serie A
    78,   # Germany Bundesliga
    61,   # France Ligue 1
    88,   # Netherlands Eredivisie
    203,  # Serbia SuperLiga
}

# Konzervativna zona kvota za single leg (tipsterska intuicija)
SAFE_ODDS_MIN = 1.10
SAFE_ODDS_MAX = 1.40

OPTIMAL_ODDS_LOW = 1.15
OPTIMAL_ODDS_HIGH = 1.30


def _score_leg(leg: Dict[str, Any]) -> float:
    """
    Heuristički scoring jednog lega.

    Ideja:
    - top lige + stabilne kvote = bonus
    - previše visoke kvote = penal
    - market diversity i tip tržišta (goals vs 1X2 vs BTTS) može se kasnije dodatno doterivati
    """
    score = 0.0

    league_id = leg.get("league_id")
    odds = float(leg.get("odds", 0.0) or 0.0)
    market_family = (leg.get("market_family") or leg.get("market") or "").upper()

    # 1) Liga
    if league_id in TOP_LEAGUE_IDS:
        score += 5.0  # premium ligama dajemo boost
    else:
        score += 2.0  # ostale lige – mali, ali pozitivan doprinos

    # 2) Kvote – sweet spot 1.15–1.30
    if odds <= 1.01:
        score -= 4.0  # praktično beskorisno
    elif SAFE_ODDS_MIN <= odds <= SAFE_ODDS_MAX:
        # u okviru konzervativnog raspona
        score += 4.0
        if OPTIMAL_ODDS_LOW <= odds <= OPTIMAL_ODDS_HIGH:
            score += 3.0  # zlatna zona
        elif odds > OPTIMAL_ODDS_HIGH:
            score -= 1.0  # bliže 1.40 → malo riskantnije
    else:
        # van raspona 1.10–1.40
        if odds < SAFE_ODDS_MIN:
            score -= 2.0
        else:  # odds > 1.40
            score -= 5.0

    # 3) Market family – goals family tipično malo stabilniji od čistih 1X2 na “divljim” ligama
    if market_family in {"GOALS", "O/U"}:
        score += 1.5
    elif market_family in {"BTTS"}:
        score += 1.0
    elif market_family in {"1X2", "WIN"}:
        score += 0.5

    return score


def score_ticket(ticket: Dict[str, Any]) -> float:
    """
    Scoring celog tiketa na skali ~50–95.

    Heuristike:
    - kraći tiket (2–3 meča) = veći score
    - previše mečeva = penal
    - market diversity (mix goals/BTTS/DC/1X2) = plus
    - top lige / stabilne kvote po legu = veliki deo score-a
    """
    legs: List[Dict[str, Any]] = ticket.get("legs") or []
    if not legs:
        return 0.0

    n_legs = len(legs)

    # 1) Osnovna vrednost
    base = 60.0

    # 2) Doprinos pojedinačnih legova
    leg_scores = [_score_leg(leg) for leg in legs]
    avg_leg_score = sum(leg_scores) / max(1, len(leg_scores))

    score = base + avg_leg_score

    # 3) Kazna / bonus za dužinu tiketa
    if n_legs == 1:
        score += 3.0  # single je ok, ali naš fokus je na 2–4
    elif n_legs == 2:
        score += 7.0
    elif n_legs == 3:
        score += 5.0
    elif n_legs == 4:
        score += 0.0
    elif n_legs == 5:
        score -= 4.0
    else:
        score -= 6.0  # 6+ legova – tipsterski rizik

    # 4) Market diversity na nivou tiketa
    families = set((leg.get("market_family") or leg.get("market") or "").upper() for leg in legs)
    families.discard("")
    if len(families) >= 3:
        score += 5.0  # mix (U3.5 + O1.5 + BTTS) – idealno
    elif len(families) == 2:
        score += 3.0
    else:
        # monolitni tiket – čist penal
        score -= 4.0

    # 5) Blaga korekcija po ukupnoj kvoti (već obrađena u builderima, ovo je samo finalni fine-tune)
    total_odds = float(ticket.get("total_odds", 0.0) or 0.0)
    if 2.0 <= total_odds <= 3.0:
        score += 2.0
    elif total_odds > 3.0:
        score -= 2.0

    # Clamp na razuman opseg
    if score < 40.0:
        score = 40.0
    if score > 95.0:
        score = 95.0

    return score


def annotate_ticket_sets_with_score(ticket_sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prolazi kroz sve setove i sve tikete i dodaje 'score' polje bazirano na heurističkom scoringu.
    """
    for s in ticket_sets or []:
        tickets = s.get("tickets") or []
        for t in tickets:
            t["score"] = score_ticket(t)
    return ticket_sets


def get_adaptive_min_score(fixtures_count: int, raw_total_tickets: int) -> float:
    """
    Dinamički threshold za AI filter, zasnovan na:
    - broju današnjih mečeva (fixtures_count)
    - broju kandidovanih tiketa pre filtera (raw_total_tickets)

    Tipsterska logika:
    - kad je malo mečeva / malo kandidata → spuštamo prag (ne forsiramo “savršene” tikete)
    - kad je bogat dan i ima puno kandidata → dižemo prag (biramo samo crème de la crème)
    """
    # osnovni prag (ono što si do sada koristio)
    base = 62.0

    # 1) Količina mečeva
    if fixtures_count <= 40:
        base -= 6.0         # “mršav” dan – nemamo luksuz da budemo ultra-picki
    elif fixtures_count <= 80:
        base -= 3.0
    elif fixtures_count >= 200:
        base += 3.0         # vikendi / puno mečeva – možemo da biramo strože
    elif fixtures_count >= 120:
        base += 1.5

    # 2) Koliko je uopšte kandidovanih tiketa
    if raw_total_tickets <= 3:
        base -= 4.0         # ima malo tiketa – bolje da ih ne ubijemo previsokim pragom
    elif raw_total_tickets <= 6:
        base -= 2.0
    elif raw_total_tickets >= 15:
        base += 3.0
    elif raw_total_tickets >= 10:
        base += 1.5

    # Clamp
    if base < 52.0:
        base = 52.0
    if base > 75.0:
        base = 75.0

    return base
