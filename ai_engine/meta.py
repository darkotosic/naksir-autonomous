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

EU_LEAGUE_WEIGHTS: Dict[int, int] = {
    2: 100,
    3: 96,
    5: 92,
    39: 95,
    78: 93,
    61: 91,
    135: 93,
    140: 94,
    88: 85,
    94: 80,
    203: 76,
    566: 72,
}

# Konzervativan raspon kvota po legu
SAFE_ODDS_MIN = 1.10
SAFE_ODDS_MAX = 1.40
OPTIMAL_ODDS_LOW = 1.15
OPTIMAL_ODDS_HIGH = 1.30

RISK_BY_FAMILY: Dict[str, int] = {
    "GOALS": 42,
    "GOALS_UNDER": 48,
    "HT_GOALS": 55,
    "BTTS": 60,
    "RESULT": 50,
    "DOUBLE_CHANCE": 25,
    "DRAW": 58,
}


def _clamp(val: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, val))


def _league_weight(league_id: Any) -> float:
    try:
        lid = int(league_id)
    except Exception:
        return 35.0

    if lid in EU_LEAGUE_WEIGHTS:
        return float(EU_LEAGUE_WEIGHTS[lid])
    if lid in TOP_LEAGUE_IDS:
        return 75.0
    return 45.0


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
    score += _league_weight(league_id) / 25.0

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
    Backwards compatible wrapper that surfaces the new evaluation score.
    """
    return evaluate_ticket(ticket)["score"]


def _kickoff_window(legs: List[Dict[str, Any]]) -> float:
    times: List[int] = []
    for leg in legs:
        kickoff = str(leg.get("kickoff") or "")
        try:
            times.append(int(kickoff.replace("-", "").replace(":", "")[8:12]))
        except Exception:
            continue
    if not times:
        return 0.0
    return float(max(times) - min(times))


def evaluate_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expanded AI evaluator: 12 faktora + tekstualni reasoning + risk heatmap.
    """

    legs = ticket.get("legs") or []
    if not isinstance(legs, list) or not legs:
        return {
            "score": 0.0,
            "factors": [],
            "reasoning": "No legs present.",
            "risk_heatmap": {},
            "risk_tags": ["invalid"],
            "analysis_mode": "autonomous_v2",
        }

    factors: List[Dict[str, Any]] = []
    risk_tags: Set[str] = set()

    leg_scores: List[float] = []
    league_weights: List[float] = []
    odds_list: List[float] = []
    families: Set[str] = set()
    model_scores: List[float] = []

    for leg in legs:
        if not isinstance(leg, dict):
            continue
        leg_scores.append(_score_leg(leg))
        league_weights.append(_league_weight(leg.get("league_id")))
        try:
            odds_list.append(float(leg.get("odds", 0.0) or 0.0))
        except Exception:
            odds_list.append(0.0)
        fam = str(leg.get("market_family") or leg.get("market") or "").upper()
        if fam:
            families.add(fam)
            if fam in {"BTTS", "DRAW"}:
                risk_tags.add("high_variance")
            if fam in {"DOUBLE_CHANCE"}:
                risk_tags.add("safe_guard")
        try:
            model_scores.append(float(leg.get("model_score") or leg.get("confidence") or 0.0))
        except Exception:
            model_scores.append(0.0)

    avg_leg_score = sum(leg_scores) / max(1, len(leg_scores))
    avg_league_weight = sum(league_weights) / max(1, len(league_weights))
    avg_odds = sum(odds_list) / max(1, len(odds_list))
    total_odds = float(ticket.get("total_odds") or 0.0)
    kickoff_window = _kickoff_window(legs)

    def _add_factor(name: str, value: float, weight: float, reason: str) -> None:
        factors.append(
            {
                "name": name,
                "value": _clamp(value),
                "weight": weight,
                "reason": reason,
            }
        )

    _add_factor(
        "league_quality",
        avg_league_weight,
        1.2,
        f"Prosek ligaške težine {avg_league_weight:.1f} (EU prioritet).",
    )

    odds_sweet = 100.0 - abs(((avg_odds or 1.3) - 1.25) * 120)
    _add_factor(
        "odds_stability",
        odds_sweet,
        1.0,
        f"Prosek kvota {avg_odds:.2f} sa sweet-spot ciljem 1.15–1.30.",
    )

    ticket_len = len(legs)
    length_score = {1: 65.0, 2: 78.0, 3: 95.0, 4: 90.0, 5: 80.0}.get(
        ticket_len, 65.0
    )
    _add_factor(
        "ticket_length",
        length_score,
        1.0,
        f"{ticket_len} leg(s) balans za 2+ tiket.",
    )

    diversity_score = 60.0 + (len(families) * 8.0)
    _add_factor(
        "market_diversity",
        diversity_score,
        0.9,
        f"{len(families)} market familija obezbeđuje miks.",
    )

    total_window = 100.0 - abs((total_odds or 2.5) - 2.6) * 25
    _add_factor(
        "total_odds_window",
        total_window,
        1.1,
        f"Ukupna kvota {total_odds:.2f} cilja 2.0–3.2 prozor.",
    )

    _add_factor(
        "kickoff_alignment",
        100.0 - min(kickoff_window, 1800.0) / 20.0,
        0.6,
        "Raspored mečeva kompaktan, smanjuje simultane rizike.",
    )

    eu_ratio = sum(1 for w in league_weights if w >= 75.0) / max(1, len(league_weights))
    _add_factor(
        "eu_bias",
        eu_ratio * 100.0,
        1.0,
        f"{eu_ratio*100:.0f}% legova iz top EU liga.",
    )

    cap_penalty = max(odds_list) if odds_list else 0.0
    cap_score = 100.0 - max(0.0, (cap_penalty - 1.55) * 80.0)
    _add_factor(
        "market_caps",
        cap_score,
        0.9,
        f"Najviša kvota po legu {cap_penalty:.2f} drži rizik pod kontrolom.",
    )

    model_signal = (
        sum(model_scores) / max(1, len(model_scores)) if any(model_scores) else 55.0
    )
    _add_factor(
        "model_alignment",
        model_signal,
        0.8,
        "Average model/confidence score across legs.",
    )

    form_signal = 70.0
    if any("form" in (leg or {}) for leg in legs if isinstance(leg, dict)):
        form_signal = 82.0
    _add_factor(
        "team_form",
        form_signal,
        0.7,
        "Form signali dostupni kroz in-depth sloj.",
    )

    mix_balance = 75.0 if len(families) >= 2 else 60.0
    _add_factor(
        "builder_mix",
        mix_balance,
        0.7,
        "Mix buildera balansira GOALS/HT/DC fallback logiku.",
    )

    risk_cushion = 100.0 if "safe_guard" in risk_tags else 72.0
    _add_factor(
        "risk_cushion",
        risk_cushion,
        0.6,
        "Double chance / konzervativni izbori pružaju tampon zonu.",
    )

    base_confidence = 60.0 + avg_leg_score
    _add_factor(
        "leg_quality",
        base_confidence,
        1.1,
        "Prosečan leg score uvećan EU težinom.",
    )

    total_weight = sum(f["weight"] for f in factors)
    weighted_sum = sum(f["value"] * f["weight"] for f in factors)
    score = _clamp(weighted_sum / max(total_weight, 1.0))

    risk_heatmap: Dict[str, Dict[str, float | int]] = {}
    for fam in families:
        risk_heatmap[fam] = {
            "legs": sum(1 for l in legs if str(l.get("market_family") or l.get("market") or "").upper() == fam),
            "risk": RISK_BY_FAMILY.get(fam, 50),
        }

    top_reasons = sorted(factors, key=lambda x: x["weight"] * x["value"], reverse=True)[:4]
    reasoning = " | ".join(f["reason"] for f in top_reasons)

    return {
        "score": round(score, 1),
        "factors": factors,
        "reasoning": reasoning,
        "risk_heatmap": risk_heatmap,
        "risk_tags": sorted(risk_tags) or ["balanced"],
        "analysis_mode": "autonomous_v2",
    }


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
                eval_result = evaluate_ticket(t)
                enriched_legs: List[Dict[str, Any]] = []
                for leg in legs:
                    if not isinstance(leg, dict):
                        continue
                    leg.setdefault("league_weight", _league_weight(leg.get("league_id")))
                    leg.setdefault("team_form", leg.get("team_form") or leg.get("form") or "unknown")
                    leg.setdefault("analysis_mode", eval_result["analysis_mode"])
                    enriched_legs.append(leg)

                t["legs"] = enriched_legs
                t["score"] = eval_result["score"]
                t["ai_factors"] = eval_result["factors"]
                t["ai_reasoning"] = eval_result["reasoning"]
                t["risk_heatmap"] = eval_result["risk_heatmap"]
                t["risk_tags"] = eval_result["risk_tags"]
                t["analysis_mode"] = eval_result["analysis_mode"]
                clean_tickets.append(t)
            except Exception:
                # bilo koji problem u scoringu → preskačemo tiket
                continue

        s["tickets"] = clean_tickets
        if clean_tickets:
            new_sets.append(s)

    ticket_sets["sets"] = new_sets
    if ticket_sets.get("analysis_mode") is None:
        ticket_sets["analysis_mode"] = "autonomous_v2"
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
