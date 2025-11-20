# core_data/cleaners.py
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _safe_response(raw: Any) -> List[Dict[str, Any]]:
    """
    Helper: vrati listu iz raw API odgovora.
    API-FOOTBALL standardno vraća dict sa ključem 'response'.
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        resp = raw.get("response")
        if isinstance(resp, list):
            return resp
        if resp is None and isinstance(raw.get("results"), int):
            # fallback – neki endpointi
            return []
    if isinstance(raw, list):
        return raw
    return []


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

def clean_fixtures(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalizacija fixtures odgovora.

    Cilj:
    - vrati listu fixture dict-ova u API-FOOTBALL formatu (fixture/league/teams)
    - isfiltriraj očigledno neupotrebljive (bez ID, bez timova, cancel-ovane)
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

        # minimalni sanity check
        if fid is None or lid is None or not home or not away:
            continue

        status = (fixture.get("status") or {}).get("short")
        # ignoriši završene / otkazane / prekinute
        if status in {"FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"}:
            continue

        cleaned.append(item)

    return cleaned


# ---------------------------------------------------------------------------
# ODDS – full improved mapping
# ---------------------------------------------------------------------------

def _map_market(bet_name: str, label: str) -> Optional[str]:
    """
    Mapira (bet_name, label) iz API-FOOTBALL strukture u interni market kod.

    Vraća:
      - "HOME", "AWAY", "DRAW"
      - "1X", "X2", "12"
      - "O05", "O15", "O25", "O35"
      - "U25", "U35"
      - "HT_O05"
      - "BTTS_YES", "BTTS_NO"
      - ili None ako nas market ne zanima direktno
    """
    bn = (bet_name or "").strip().lower()
    lv = (label or "").strip().lower()

    # 1) Match Winner
    if bn == "match winner":
        if lv in {"home", "1"}:
            return "HOME"
        if lv in {"away", "2"}:
            return "AWAY"
        if lv in {"draw", "x"}:
            return "DRAW"
        return None

    # 2) Double Chance
    if bn == "double chance":
        # tipična imena u API-FOOTBALL: "1X", "12", "X2"
        if lv in {"1x", "1 or draw"}:
            return "1X"
        if lv in {"x2", "2x", "draw or 2"}:
            return "X2"
        if lv in {"12", "1 or 2"}:
            return "12"
        return None

    # 3) Goals Over/Under – full time
    if bn == "goals over/under":
        # primeri: "Over 0.5", "Under 3.5"
        parts = lv.split()
        if len(parts) != 2:
            return None
        side, line = parts[0], parts[1]  # npr. "over", "2.5"

        if side == "over":
            if line == "0.5":
                return "O05"
            if line == "1.5":
                return "O15"
            if line == "2.5":
                return "O25"
            if line == "3.5":
                return "O35"
        if side == "under":
            if line == "2.5":
                return "U25"
            if line == "3.5":
                return "U35"
        return None

    # 4) Goals Over/Under – 1st half → HT_O05
    if "1st half" in bn and ("goals over/under" in bn or "goals" in bn):
        # "Over 0.5", "Under 0.5", itd.
        parts = lv.split()
        if len(parts) != 2:
            return None
        side, line = parts[0], parts[1]
        if side == "over" and line == "0.5":
            return "HT_O05"
        return None

    # 5) Both Teams To Score
    if "both teams to score" in bn or "btts" in bn:
        if lv in {"yes", "y"}:
            return "BTTS_YES"
        if lv in {"no", "n"}:
            return "BTTS_NO"
        # ponekad value bude "Yes" / "No" sa velikim početnim slovom
        if lv in {"da"}:  # ako bi negde bilo lokalizovano
            return "BTTS_YES"
        if lv in {"ne"}:
            return "BTTS_NO"
        return None

    # ostalo za sada ignorišemo
    return None


def clean_odds(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalizacija odds odgovora.

    Vraća flatten listu dict-ova:
      {
        "fixture_id": int,
        "league_id": int,
        "bookmaker": str,
        "bet_name": str,     # npr. "Goals Over/Under"
        "label": str,        # npr. "Over 2.5"
        "market": str | None,# interni market kod: O15, U35, HOME, 1X, HT_O05, BTTS_YES...
        "odd": float,
      }

    Čak i kada market nije prepoznat (market=None), red se čuva – to daje
    puniji dataset za kasniju analitiku, a builderi koriste samo ono što znaju.
    """
    response = _safe_response(raw)
    cleaned: List[Dict[str, Any]] = []

    for item in response:
        if not isinstance(item, dict):
            continue

        fixture = item.get("fixture") or {}
        league = item.get("league") or {}

        fixture_id = fixture.get("id")
        league_id = league.get("id")

        if fixture_id is None or league_id is None:
            continue

        for bm in item.get("bookmakers") or []:
            bookmaker_name = (bm.get("name") or "").strip() or "Unknown"

            for bet in bm.get("bets") or []:
                bet_name = (bet.get("name") or "").strip()
                if not bet_name:
                    continue

                for v in bet.get("values") or []:
                    label = (v.get("value") or "").strip()
                    odd_str = v.get("odd")

                    try:
                        odd_val = float(odd_str)
                    except (TypeError, ValueError):
                        continue

                    market = _map_market(bet_name, label)

                    cleaned.append(
                        {
                            "fixture_id": int(fixture_id),
                            "league_id": int(league_id),
                            "bookmaker": bookmaker_name,
                            "bet_name": bet_name,
                            "label": label,
                            "market": market,
                            "odd": odd_val,
                        }
                    )

    return cleaned
