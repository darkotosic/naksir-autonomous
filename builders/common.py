# builders/common.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Zadržavamo listu preferiranih liga radi kasnijeg ponderisanja ili specijalnih pravila,
# ali je VIŠE NE KORISTIMO kao hard filter u is_fixture_playable (global pool).
ALLOWED_LEAGUES: Set[int] = {
    39,   # England Premier League
    140,  # Spain La Liga
    135,  # Italy Serie A
    78,   # Germany Bundesliga
    61,   # France Ligue 1
    88,   # Netherlands Eredivisie
    203,  # Serbia SuperLiga
}


def parse_kickoff(fixture: Dict[str, Any]) -> Optional[str]:
    """
    Vraća ISO datetime string iz fixture["fixture"]["date"],
    ili None ako je invalidan.
    """
    fx = fixture.get("fixture") or {}
    dt_str = fx.get("date")
    if not dt_str:
        return None
    # API-Football format je već ISO; samo validiramo
    try:
        # Ako je "Z" na kraju, pretvorimo u +00:00
        _ = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt_str
    except Exception:
        return None


def is_fixture_playable(fixture: Dict[str, Any]) -> bool:
    """
    Global pool varijanta:

    - DOZVOLJAVA SVE LIGE (nema više ALLOWED_LEAGUES filtera)
    - i dalje traži da:
        * fixture ima league_id
        * status je NS / TBD / None (nije počelo)
    """
    league = fixture.get("league") or {}
    lid = league.get("id")

    # Minimalna validacija: mora da postoji league_id
    if lid is None:
        return False

    fx = fixture.get("fixture") or {}
    status = (fx.get("status") or {}).get("short")

    # Dozvoljavamo samo mečeve koji još nisu krenuli
    if status not in (None, "NS", "TBD"):
        return False

    return True


def build_odds_index(odds_list: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    Grupisanje clean-ovanih odds po fixture_id.
    Očekuje strukturu iz clean_odds:
    {
      "fixture_id": int,
      "league_id": int,
      "bet_name": str,
      "label": str,
      "odd": float,
      ...
    }
    """
    index: Dict[int, List[Dict[str, Any]]] = {}
    for row in odds_list or []:
        fid = row.get("fixture_id")
        if fid is None:
            continue
        index.setdefault(fid, []).append(row)
    return index


def get_market_odds(
    odds_index: Dict[int, List[Dict[str, Any]]],
    fixture_id: int,
    bet_name: str,
    value_label: str,
) -> Optional[float]:
    """
    Pronalazi kvotu za zadati market:

    - bet_name npr. "Goals Over/Under"
    - value_label npr. "Over 2.5"

    Poboljšanja:
    - case-insensitive i trim сравнение (manje pucanja na "goals over/under", "Over 2.5 ")
    - vraća NAJNIŽU kvotu (konzervativno) među bookmakerima ili None.
    """
    rows = odds_index.get(fixture_id) or []
    found: List[float] = []

    bet_name_key = (bet_name or "").strip().lower()
    label_key = (value_label or "").strip().lower()

    for r in rows:
        r_bet = (r.get("bet_name") or "").strip().lower()
        r_label = (r.get("label") or "").strip().lower()

        if r_bet != bet_name_key:
            continue
        if r_label != label_key:
            continue

        odd_val = r.get("odd")
        try:
            if odd_val is not None:
                found.append(float(odd_val))
        except (TypeError, ValueError):
            continue

    if not found:
        return None
    return min(found)


def build_leg(
    fixture: Dict[str, Any],
    *,
    market: str,
    market_family: str,
    pick: str,
    odds: float,
) -> Optional[Dict[str, Any]]:
    """
    Gradi standardizovan 'leg' dict iz fixture-a + meta informacija.
    """
    league = fixture.get("league") or {}
    teams = fixture.get("teams") or {}
    fx = fixture.get("fixture") or {}

    fixture_id = fx.get("id")
    league_id = league.get("id")
    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")

    if not fixture_id or not league_id or not home or not away:
        return None

    kickoff = parse_kickoff(fixture)
    if kickoff is None:
        return None

    leg = {
        "fixture_id": int(fixture_id),
        "league_id": int(league_id),
        "league_name": league.get("name"),
        "league_country": league.get("country"),
        "home": home,
        "away": away,
        "kickoff": kickoff,  # ISO string
        "market": market,
        "market_family": market_family,
        "pick": pick,
        "odds": float(odds),
    }
    return leg
