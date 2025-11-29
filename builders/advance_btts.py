from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime


# Liga whitelist (možeš da prilagodiš po potrebi)
ALLOW_LEAGUES: List[int] = [
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    3,
    14,
    2,
    848,
    38,
    78,
    79,
    61,
    62,
    218,
    88,
    89,
    203,
    40,
    119,
    136,
    736,
    207,
]


def _index_fixtures(fixtures: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    for fx in fixtures:
        try:
            fid = int((fx.get("fixture") or {}).get("id"))
        except Exception:
            continue
        by_id[fid] = fx
    return by_id


def _extract_basic_meta(fx: Dict[str, Any]) -> Tuple[int, str, str, str, str, str]:
    fixture = fx.get("fixture") or {}
    league = fx.get("league") or {}
    teams = fx.get("teams") or {}

    league_id = int(league.get("id") or 0)
    league_name = str(league.get("name") or "").strip()
    league_country = str(league.get("country") or "").strip()

    home = str((teams.get("home") or {}).get("name") or "").strip()
    away = str((teams.get("away") or {}).get("name") or "").strip()

    # kickoff kao ISO string (ako ne uspe, prazan string)
    dt_raw = fixture.get("date")
    kickoff_iso = ""
    if isinstance(dt_raw, str):
        kickoff_iso = dt_raw
    elif isinstance(dt_raw, datetime):
        kickoff_iso = dt_raw.isoformat()

    return league_id, league_name, league_country, home, away, kickoff_iso


def _is_fixture_playable(fx: Dict[str, Any]) -> bool:
    fixture = fx.get("fixture") or {}
    status = (fixture.get("status") or {}).get("short")
    if status in {"FT", "AET", "PEN", "CANC", "ABD", "PST", "AWD", "WO"}:
        return False
    return True


def advance_Btts(
    fixtures: List[Dict[str, Any]],
    odds_rows: List[Dict[str, Any]],
    max_legs: int = 500,
    min_odd: float = 1.20,
    max_odd: float = 1.60,
) -> List[Dict[str, Any]]:
    """
    Napredni BTTS builder.

    Ulaz:
      - fixtures: originalni API-FOOTBALL fixtures (posle clean_fixtures, dakle list[dict])
      - odds_rows: canonical odds redovi iz clean_odds (fixture_id, league_id, market, odd, ...)
      - max_legs: hard cap koliko maksimalno BTTS legova vraćamo

    Logika:
      - filtrira canonical market == "BTTS_YES"
      - kvota u [min_odd, max_odd]
      - liga u ALLOW_LEAGUES
      - fixture mora da bude "playable" (nije završen/otkazan)
      - po jednom fixture_id vraća max 1 leg
    """
    fixtures_by_id = _index_fixtures(fixtures)

    # 1) pripremi kandidatske redove iz odds
    candidate_rows: List[Dict[str, Any]] = []
    for row in odds_rows:
        try:
            if row.get("market") != "BTTS_YES":
                continue
            odd = float(row.get("odd"))
        except Exception:
            continue

        if odd < min_odd or odd > max_odd:
            continue

        fid = row.get("fixture_id")
        lid = row.get("league_id")
        if fid is None or lid is None:
            continue

        try:
            lid_int = int(lid)
        except Exception:
            continue

        if lid_int not in ALLOW_LEAGUES:
            continue

        fx = fixtures_by_id.get(int(fid))
        if not fx:
            continue

        if not _is_fixture_playable(fx):
            continue

        candidate_rows.append(row)

    # 2) deduplikacija po fixture_id – uzmi najbolju kvotu (najveću) po fixture-u
    best_by_fixture: Dict[int, Dict[str, Any]] = {}
    for row in candidate_rows:
        fid = int(row["fixture_id"])
        prev = best_by_fixture.get(fid)
        if prev is None or float(row["odd"]) > float(prev["odd"]):
            best_by_fixture[fid] = row

    legs: List[Dict[str, Any]] = []

    for fid, row in best_by_fixture.items():
        fx = fixtures_by_id.get(fid)
        if not fx:
            continue

        league_id, league_name, league_country, home, away, kickoff_iso = _extract_basic_meta(fx)

        leg = {
            "fixture_id": fid,
            "league_id": league_id,
            "league_name": league_name,
            "league_country": league_country,
            "home": home,
            "away": away,
            "kickoff": kickoff_iso,
            "market": "BTTS_YES",
            "selection": "YES",
            "odd": float(row["odd"]),
            "bookmaker": row.get("bookmaker") or "",
            "bet_name": row.get("bet_name") or "",
            "label": row.get("label") or "",
            # meta za engine/AI
            "tags": ["BTTS", "ADVANCED", "ALLOW_LEAGUE"],
            "source": "advance_btts",
            "score_raw": None,  # popunjava kasnije AI layer / heuristika
        }

        legs.append(leg)
        if len(legs) >= max_legs:
            break

    return legs


# alias za konzistentnost naming-a ako budeš hteo da zoveš kao builder funkciju
def build_advanced_btts_legs(
    fixtures: List[Dict[str, Any]],
    odds_rows: List[Dict[str, Any]],
    max_legs: int = 500,
    min_odd: float = 1.20,
    max_odd: float = 1.60,
) -> List[Dict[str, Any]]:
    return advance_Btts(
        fixtures=fixtures,
        odds_rows=odds_rows,
        max_legs=max_legs,
        min_odd=min_odd,
        max_odd=max_odd,
  )
