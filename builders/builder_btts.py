# builders/builder_btts.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from builders.mixer import mix_tickets

ALLOWED_LEAGUES = {
    39, 140, 135, 78, 61, 88, 203,
}

ODDS_MIN = 1.10
ODDS_MAX = 1.40


def _parse_kickoff(fixture: Dict[str, Any]) -> Optional[datetime]:
    dt_str = fixture.get("fixture", {}).get("date")
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_market_odds(
    odds: Dict[str, Any],
    fixture_id: int,
    bet_name: str,
    value_label: str,
) -> Optional[float]:
    for item in odds.get("response", []):
        fx = item.get("fixture", {})
        if fx.get("id") != fixture_id:
            continue
        for book in item.get("bookmakers", []):
            for bet in book.get("bets", []):
                if bet.get("name") != bet_name:
                    continue
                for val in bet.get("values", []):
                    if val.get("value") == value_label:
                        try:
                            odd = float(val.get("odd"))
                        except (TypeError, ValueError):
                            continue
                        return odd
    return None


def build_btts_legs(
    fixtures: Dict[str, Any],
    odds: Dict[str, Any],
    want_yes: bool = True,
    max_legs: int = 100,
) -> List[Dict[str, Any]]:
    """
    Tržište: Both Teams to Score (BTTS).
    Ako je want_yes=True -> BTTS Yes
    Ako je want_yes=False -> BTTS No
    """
    legs: List[Dict[str, Any]] = []

    value_label = "Yes" if want_yes else "No"
    market_code = "BTTS_YES" if want_yes else "BTTS_NO"
    pick_label = "Both Teams to Score – Yes" if want_yes else "Both Teams to Score – No"

    for f in fixtures.get("response", []):
        league = f.get("league", {}) or {}
        league_id = league.get("id")
        if league_id is None or league_id not in ALLOWED_LEAGUES:
            continue

        fixture_info = f.get("fixture", {}) or {}
        fixture_id = fixture_info.get("id")
        if fixture_id is None:
            continue

        kickoff_dt = _parse_kickoff(f)
        if kickoff_dt is None:
            continue

        odd_val = _get_market_odds(
            odds=odds,
            fixture_id=fixture_id,
            bet_name="Both Teams to Score",
            value_label=value_label,
        )
        if odd_val is None:
            continue
        if not (ODDS_MIN <= odd_val <= ODDS_MAX):
            continue

        home_team = f.get("teams", {}).get("home", {}).get("name")
        away_team = f.get("teams", {}).get("away", {}).get("name")
        if not home_team or not away_team:
            continue

        leg = {
            "fixture_id": fixture_id,
            "league_id": league_id,
            "league_name": league.get("name"),
            "league_country": league.get("country"),
            "home": home_team,
            "away": away_team,
            "kickoff": fixture_info.get("date"),
            "market": market_code,
            "pick": pick_label,
            "odds": odd_val,
        }
        legs.append(leg)

    legs.sort(key=lambda x: x["odds"], reverse=True)
    return legs[:max_legs]
