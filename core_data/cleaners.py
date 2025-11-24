# core_data/cleaners.py
from __future__ import annotations
from typing import Any, Dict, List
import json


# -----------------------------------------------------------------------
# Canonical markets used across all builders and odds normalization
# -----------------------------------------------------------------------
DOC_MARKETS = {
    "btts": [
        "Both Teams To Score",
        "BTTS",
        "Goal",
        "GG",
        "Team to Score",
    ],
    "over_under": [
        "Over/Under",
        "Total Goals",
        "Goals Over/Under",
        "O/U",
        "Totals",
    ],
    "ht_goals": [
        "HT Over/Under",
        "Half Time Over/Under",
        "First Half Goals",
        "1st Half - Over/Under",
    ],
}


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------
def _safe_response(raw: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """Return API-Football 'response' safely."""
    return raw.get(key) or raw.get("response") or []


def _normalize_ou_value(txt: str) -> str:
    """
    Normalizes Over/Under goal value string into canonical form:
    "Over 2.5", "Under 1.5", etc.
    """
    if not txt:
        return txt
    t = txt.strip().replace(" ", "")
    if "Over" in txt or "over" in txt:
        val = txt.lower().replace("over", "").strip()
        return f"Over {val}"
    if "Under" in txt or "under" in txt:
        val = txt.lower().replace("under", "").strip()
        return f"Under {val}"
    return txt


# -----------------------------------------------------------------------
# BEST MARKET ODDS (canonical)
# FIXED — now fully indented and valid Python
# -----------------------------------------------------------------------
def best_market_odds(bookmakers: list) -> dict:
    """
    Extracts best odds for canonical markets:
    - BTTS {Yes/No}
    - Over/Under {Over X.X, Under X.X}
    - HT Over/Under {Over X.X, Under X.X}

    Results example:
    {
        "BTTS": {"Yes": 1.72, "No": 2.05},
        "Over/Under": {"Over 2.5": 1.85, "Under 2.5": 1.95},
        "HT_Over/Under": {"Over 0.5": 1.30, "Under 0.5": 3.40},
    }
    """
    odds_best: dict = {}

    for bm in bookmakers or []:
        for market in bm.get("bets", []):
            mname = (market.get("name") or "").strip()

            # -------------------------
            # BTTS
            # -------------------------
            if any(mname.startswith(x) for x in DOC_MARKETS["btts"]):
                for item in market.get("values", []):
                    lbl_raw = (item.get("value") or "").strip()
                    low = lbl_raw.lower()

                    if low in ("yes", "gg", "goal"):
                        key = "Yes"
                    elif low in ("no", "ng", "nogoal"):
                        key = "No"
                    else:
                        key = lbl_raw

                    odds_best.setdefault("BTTS", {})
                    odds_best["BTTS"][key] = float(item.get("odd") or 0)

            # -------------------------
            # FT Over/Under
            # -------------------------
            if any(mname.startswith(x) for x in DOC_MARKETS["over_under"]):
                for item in market.get("values", []):
                    lbl = _normalize_ou_value(item.get("value") or "")
                    odds_best.setdefault("Over/Under", {})
                    odds_best["Over/Under"][lbl] = float(item.get("odd") or 0)

            # -------------------------
            # HT Over/Under
            # -------------------------
            if any(mname.startswith(x) for x in DOC_MARKETS["ht_goals"]):
                for item in market.get("values", []):
                    lbl = _normalize_ou_value(item.get("value") or "")
                    odds_best.setdefault("HT_Over/Under", {})
                    odds_best["HT_Over/Under"][lbl] = float(item.get("odd") or 0)

    return odds_best


# -----------------------------------------------------------------------
# CLEAN FIXTURES
# -----------------------------------------------------------------------
def clean_fixtures(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    fixtures = []
    for fx in _safe_response(raw, "response"):
        fixture_id = fx.get("fixture", {}).get("id")
        league = fx.get("league", {})
        teams = fx.get("teams", {})
        fixtures.append(
            {
                "fixture_id": fixture_id,
                "kickoff": fx.get("fixture", {}).get("date"),
                "league_id": league.get("id"),
                "league_name": league.get("name"),
                "league_country": league.get("country"),
                "home": teams.get("home", {}).get("name"),
                "away": teams.get("away", {}).get("name"),
            }
        )
    return fixtures


# -----------------------------------------------------------------------
# MAP ODDS MARKET → canonical code inside odds dictionary
# -----------------------------------------------------------------------
def _map_market(name: str, value: str) -> str | None:
    """
    Return canonical market code like:
    O15, O25, U35, HT_O05, BTTS_YES, BTTS_NO, DC_1X...
    """
    if not name:
        return None

    n = name.lower()

    if "both teams" in n or "btts" in n:
        v = value.lower()
        if v in ("yes", "gg", "goal"):
            return "BTTS_YES"
        if v in ("no", "ng", "nogoal"):
            return "BTTS_NO"

    if "over" in n and value:
        try:
            g = float(value)
            if abs(g - 1.5) < 0.01:
                return "O15"
            if abs(g - 2.5) < 0.01:
                return "O25"
            if abs(g - 3.5) < 0.01:
                return "O35"
        except:
            pass

    if "under" in n and value:
        try:
            g = float(value)
            if abs(g - 3.5) < 0.01:
                return "U35"
        except:
            pass

    if "half" in n or "ht" in n:
        if "over" in n and value:
            try:
                g = float(value)
                if abs(g - 0.5) < 0.01:
                    return "HT_O05"
            except:
                pass

    if "double chance" in n or "dc" in n:
        vl = value.lower()
        if vl == "1x":
            return "DC_1X"
        if vl == "x2":
            return "DC_X2"

    return None


# -----------------------------------------------------------------------
# CLEAN ODDS
# -----------------------------------------------------------------------
def clean_odds(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    cleaned = []
    for ox in _safe_response(raw, "response"):
        fixture_id = ox.get("fixture", {}).get("id")
        bookmakers = ox.get("bookmakers", [])
        full = []

        for bm in bookmakers:
            for market in bm.get("bets", []):
                mname = (market.get("name") or "").strip()
                for v in market.get("values", []):
                    mapped = _map_market(mname, v.get("value"))
                    if mapped:
                        full.append(
                            {
                                "market": mapped,
                                "odd": float(v.get("odd") or 0),
                                "bookmaker": bm.get("name"),
                            }
                        )

        cleaned.append(
            {
                "fixture_id": fixture_id,
                "odds_full": full,
                "best": best_market_odds(bookmakers),
            }
        )

    return cleaned


# -----------------------------------------------------------------------
# CLEAN STANDINGS
# -----------------------------------------------------------------------
def clean_standings(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _safe_response(raw, "response")


# -----------------------------------------------------------------------
# CLEAN TEAM STATS
# -----------------------------------------------------------------------
def clean_team_stats(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _safe_response(raw, "response")


# -----------------------------------------------------------------------
# CLEAN H2H LAST 5
# -----------------------------------------------------------------------
def clean_h2h(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _safe_response(raw, "response")


# -----------------------------------------------------------------------
# CLEAN PREDICTIONS
# -----------------------------------------------------------------------
def clean_predictions(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _safe_response(raw, "response")


# -----------------------------------------------------------------------
# CLEAN INJURIES
# -----------------------------------------------------------------------
def clean_injuries(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    return _safe_response(raw, "response")
