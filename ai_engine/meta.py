# ai_engine/meta.py
from __future__ import annotations

from typing import Dict, Any, List


def score_ticket(ticket: Dict[str, Any]) -> float:
    """
    AI stub — trenutno čisto heuristički score 0–100.
    Kasnije zamenjuješ pravim OpenAI pozivom.

    Ideja:
    - više mečeva → manji score (više rizika)
    - veća ukupna kvota → manji score
    - 2.0–2.2 kvota, 3–4 meča → oko 70–80%
    """
    legs: List[Dict[str, Any]] = ticket.get("legs", [])
    total_odds = float(ticket.get("total_odds", 1.0))
    n_legs = len(legs) or 1

    # bazni score
    score = 85.0

    # penal po broju mečeva
    if n_legs > 3:
        score -= (n_legs - 3) * 4.0

    # penal po kvoti
    if total_odds > 2.2:
        score -= (total_odds - 2.2) * 8.0

    # clamp 0–100
    score = max(0.0, min(100.0, score))
    return round(score, 1)


def annotate_ticket_sets_with_score(ticket_sets: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prolazi kroz sve setove i tikete i dodaje "score" polje.
    Kasnije možeš da filtrišeš npr. samo score >= 62%.
    """
    for s in ticket_sets.get("sets", []):
        for t in s.get("tickets", []):
            t["score"] = score_ticket(t)
    return ticket_sets
