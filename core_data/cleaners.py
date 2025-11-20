# core_data/cleaners.py
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helper: standardize access to raw["response"]
# ---------------------------------------------------------------------------

def _safe_response(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        resp = raw.get("response")
        if isinstance(resp, list):
            return resp
        return []
    if isinstance(raw, list):
        return raw
    return []


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

def clean_fixtures(raw: Any) -> List[Dict[str, Any]]:
    response = _safe_response(raw)
    cleaned: List[Dict[str, Any]] = []

    for item in response:
        if not isinstance(item, dict):
            continue

        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}

        fid = fixture.get("id")
        lid = league.get("id")
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")

        if fid is None or lid is None or not home or not away:
            continue

        status = (fixture.get("status") or {}).get("short")
        if status in {"FT", "FT", "AET", "PEN", "CANC", "ABD", "PST", "AWD", "WO"}:
            continue

        cleaned.append(item)

    return cleaned


# ---------------------------------------------------------------------------
# MARKET MAPPING FOR ODDS
# ---------------------------------------------------------------------------

def _map_market(bet_name: str, label: str) -> Optional[str]:
    bn = (bet_name or "").strip().lower()
    lv = (label or "").strip().lower()

    # Match Winner
    if bn == "match winner":
        if lv in {"home", "1"}:
            return "HOME"
        if lv in {"draw", "x"}:
            return "DRAW"
        if lv in {"away", "2"}:
            return "AWAY"
        return None

    # Double Chance
    if bn == "double chance":
        if lv in {"1x", "1 or draw"}:
            return "1X"
        if lv in {"x2", "2x", "draw or 2"}:
            return "X2"
        if lv in {"12", "1 or 2"}:
            return "12"
        return None

    # Goals Over/Under
    if bn == "goals over/under":
        parts = lv.split()
        if len(parts) != 2:
            return None
        side, line = parts
        if side == "over":
            if line == "0.5": return "O05"
            if line == "1.5": return "O15"
            if line == "2.5": return "O25"
            if line == "3.5": return "O35"
        if side == "under":
            if line == "2.5": return "U25"
            if line == "3.5": return "U35"
        return None

    # First Half Over 0.5
    if ("1st half" in bn and "over" in lv and "0.5" in lv):
        return "HT_O05"

    # BTTS
    if "both teams to score" in bn or "btts" in bn:
        if lv == "yes": return "BTTS_YES"
        if lv == "no": return "BTTS_NO"
        return None

    return None


# ---------------------------------------------------------------------------
# ODDS
# ---------------------------------------------------------------------------

def clean_odds(raw: Any) -> List[Dict[str, Any]]:
    response = _safe_response(raw)
    cleaned: List[Dict[str, Any]] = []

    for item in response:
        if not isinstance(item, dict):
            continue

        fixture = item.get("fixture") or {}
        league = item.get("league") or {}

        fid = fixture.get("id")
        lid = league.get("id")

        if fid is None or lid is None:
            continue

        for bm in item.get("bookmakers") or []:
            bookmaker_name = (bm.get("name") or "").strip()

            for bet in bm.get("bets") or []:
                bet_name = bet.get("name")
                if not bet_name:
                    continue

                for val in bet.get("values") or []:
                    label = val.get("value")
                    odd_str = val.get("odd")
                    try:
                        odd_val = float(odd_str)
                    except:
                        continue

                    market = _map_market(bet_name, label)

                    cleaned.append(
                        {
                            "fixture_id": int(fid),
                            "league_id": int(lid),
                            "bookmaker": bookmaker_name,
                            "bet_name": bet_name,
                            "label": label,
                            "market": market,
                            "odd": odd_val,
                        }
                    )

    return cleaned


# ---------------------------------------------------------------------------
# STANDINGS
# ---------------------------------------------------------------------------

def clean_standings(raw: Any) -> List[Dict[str, Any]]:
    """
    API-Football standings response:
    response: [
        {
            "league": {...},
            "standings": [[{team stats...}, ...]]
        }
    ]
    """
    response = _safe_response(raw)
    cleaned = []

    for item in response:
        league = item.get("league") or {}
        tables = item.get("standings") or []

        for group in tables:
            for team_row in group:
                cleaned.append(
                    {
                        "league_id": league.get("id"),
                        "team_id": team_row.get("team", {}).get("id"),
                        "team_name": team_row.get("team", {}).get("name"),
                        "rank": team_row.get("rank"),
                        "points": team_row.get("points"),
                        "all": team_row.get("all"),
                    }
                )
    return cleaned


# ---------------------------------------------------------------------------
# TEAM STATS
# ---------------------------------------------------------------------------

def clean_team_stats(raw: Any) -> Dict[str, Any]:
    """
    Direct pass-through — API već vraća lep dict.
    """
    if isinstance(raw, dict):
        return raw
    return {}


# ---------------------------------------------------------------------------
# H2H
# ---------------------------------------------------------------------------

def clean_h2h(raw: Any) -> List[Dict[str, Any]]:
    """
    Vraća listu poslednjih mečeva između timova.
    """
    response = _safe_response(raw)
    cleaned = []

    for item in response:
        if not isinstance(item, dict):
            continue
        fx = item.get("fixture") or {}
        teams = item.get("teams") or {}

        cleaned.append(
            {
                "fixture_id": fx.get("id"),
                "date": fx.get("date"),
                "home": teams.get("home"),
                "away": teams.get("away"),
                "goals": item.get("goals"),
                "score": item.get("score"),
            }
        )

    return cleaned
