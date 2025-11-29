from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: standardize access to raw["response"]
# ---------------------------------------------------------------------------


def _safe_response(raw: Any) -> List[Dict[str, Any]]:
    """
    API-FOOTBALL vraća strukturu:
      { "get": "...", "response": [ ... ], "errors": [...], "results": int }

    Ovaj helper vraća uvek listu dict-ova i LOGUJE ako postoje errors.
    """
    if raw is None:
        return []

    # Klasičan API-FOOTBALL JSON
    if isinstance(raw, dict):
        errors = raw.get("errors") or []
        if errors:
            # želimo da se vidi u GitHub Actions logu
            logger.error("API-Football errors: %s", errors)

        resp = raw.get("response")
        if isinstance(resp, list):
            # filtriramo samo dict-ove
            return [x for x in resp if isinstance(x, dict)]

        # Ako nema response liste, ali results > 0, loguj anomaliju
        results = raw.get("results")
        if results not in (None, 0):
            logger.warning(
                "API-Football raw has results=%s but no usable response list. Raw snippet=%r",
                results,
                {k: raw.get(k) for k in ("get", "parameters", "errors", "results")},
            )
        return []

    # Već dobijena lista
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    return []


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------


def clean_fixtures(raw: Any) -> List[Dict[str, Any]]:
    """
    Vraća *originalne* fixture objekte iz API-ja, ali filtrirane:

    - mora da postoji fixture.id, league.id, home/away name
    - izbacuje završene / otkazane utakmice

    Ovo je važno jer builderi (common.build_leg, is_fixture_playable)
    očekuju baš API-FOOTBALL strukturu, ne custom dict.
    """
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
        # završeni / otkazani statusi koje ne želimo u builderima
        if status in {"FT", "AET", "PEN", "CANC", "ABD", "PST", "AWD", "WO"}:
            continue

        cleaned.append(item)

    return cleaned


# ---------------------------------------------------------------------------
# ODDS – canonical row-by-row format za buildere
# ---------------------------------------------------------------------------


def _map_market(bet_name: Any, label: Any) -> Optional[str]:
    bn = str(bet_name or "").lower().strip()
    lb = str(label or "").lower().strip()

    # Normalizacija
    bn = bn.replace("-", " ").replace("_", " ")
    lb = lb.replace("-", " ").replace("_", " ")

    # --- MATCH WINNER ---
    if "match winner" in bn or bn == "1x2":
        if lb in {"home", "1"}:
            return "HOME"
        if lb in {"draw", "x"}:
            return "DRAW"
        if lb in {"away", "2"}:
            return "AWAY"
        return None

    # --- DOUBLE CHANCE ---
    if "double chance" in bn:
        if lb in {"1x", "1 or draw"}:
            return "DC_1X"
        if lb in {"x2", "draw or 2"}:
            return "DC_X2"
        if lb in {"12", "1 or 2"}:
            return "DC_12"
        return None

    # --- BTTS / GG ---
    if "btts" in bn or "both teams" in bn or "to score" in bn or "goal/nogoal" in lb:
        if lb in {"yes", "gg", "goal", "goal/goal"}:
            return "BTTS_YES"
        if lb in {"no", "ng", "nogoal", "no goal"}:
            return "BTTS_NO"
        return None

    # --- OVER/UNDER total goals ---
    if "over" in lb or "under" in lb or "goals" in bn or "total" in bn:
        # pronalazi broj 1.5,2.5,3.5 iz labela
        import re

        m = re.search(r"(\d+(\.\d)?)", lb)
        if not m:
            return None
        g = float(m.group(1))

        if "over" in lb:
            if abs(g - 1.5) < 0.01:
                return "O15"
            if abs(g - 2.5) < 0.01:
                return "O25"
            if abs(g - 3.5) < 0.01:
                return "O35"
        if "under" in lb:
            if abs(g - 3.5) < 0.01:
                return "U35"
        return None

    # --- FIRST HALF ---
    if "1st half" in bn or "1h" in bn or "first half" in bn:
        if "over" in lb and ("0.5" in lb or "0 5" in lb):
            return "HT_O05"

    return None


def clean_odds(raw: Any) -> List[Dict[str, Any]]:
    """
    Vraća listu "ravnih" redova koje očekuju builderi (builders/common.py):

    {
        "fixture_id": int,
        "league_id": int,
        "bookmaker": str,
        "bet_name": str,   # npr. "Goals Over/Under"
        "label": str,      # npr. "Over 2.5"
        "market": str|None,# canonical npr. "O25"
        "odd": float,
    }
    """
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
            bookmaker_name = str(bm.get("name") or "").strip()

            for bet in bm.get("bets") or []:
                bet_name_raw = bet.get("name")
                if bet_name_raw is None:
                    continue

                for val in bet.get("values") or []:
                    label_raw = val.get("value")
                    odd_str = val.get("odd")
                    try:
                        odd_val = float(odd_str)
                    except Exception:
                        continue

                    market_code = _map_market(bet_name_raw, label_raw)

                    cleaned.append(
                        {
                            "fixture_id": int(fid),
                            "league_id": int(lid),
                            "bookmaker": bookmaker_name,
                            "bet_name": str(bet_name_raw),
                            "label": str(label_raw) if label_raw is not None else "",
                            "market": market_code,
                            "odd": odd_val,
                        }
                    )

    return cleaned


# ---------------------------------------------------------------------------
# STANDINGS
# ---------------------------------------------------------------------------


def clean_standings(raw: Any) -> List[Dict[str, Any]]:
    return _safe_response(raw)


# ---------------------------------------------------------------------------
# TEAM STATS
# ---------------------------------------------------------------------------


def clean_team_stats(raw: Any) -> List[Dict[str, Any]]:
    return _safe_response(raw)


# ---------------------------------------------------------------------------
# H2H
# ---------------------------------------------------------------------------


def clean_h2h(raw: Any) -> List[Dict[str, Any]]:
    return _safe_response(raw)


# ---------------------------------------------------------------------------
# PREDICTIONS
# ---------------------------------------------------------------------------


def clean_predictions(raw: Any) -> List[Dict[str, Any]]:
    return _safe_response(raw)


# ---------------------------------------------------------------------------
# INJURIES
# ---------------------------------------------------------------------------


def clean_injuries(raw: Any) -> List[Dict[str, Any]]:
    return _safe_response(raw)
