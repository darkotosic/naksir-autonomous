from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Tuple

from builders.builder_btts_yes import build_btts_yes_legs
from core_data.aggregator import build_all_data  # noqa: F401  # rezervisano za buduće direktno korišćenje


# Lige za BTTS Yes jutarnji feed
BTTS_LEAGUES: List[int] = [
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

BTTS_ODDS_MIN: float = 1.20
BTTS_ODDS_MAX: float = 1.60


def _index_all_data(all_data: Dict[Any, Any]) -> Dict[int, Dict[str, Any]]:
    """
    Normalizuje ključeve all_data mape u int fixture_id -> data.

    Kada je all_data generisan u Pythonu, ključevi su int.
    Kada se učita iz JSON-a, ključevi su stringovi.
    """
    index: Dict[int, Dict[str, Any]] = {}
    if not isinstance(all_data, dict):
        return index

    for k, v in all_data.items():
        try:
            fid = int(k)
        except (TypeError, ValueError):
            try:
                fid = int(getattr(k, "real", k))  # defensive
            except Exception:
                continue
        if not isinstance(v, dict):
            continue
        index[fid] = v
    return index


def _filter_fixtures_by_leagues(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fx in fixtures:
        league = fx.get("league") or {}
        try:
            league_id = int(league.get("id"))
        except (TypeError, ValueError):
            continue
        if league_id in BTTS_LEAGUES:
            out.append(fx)
    return out


def _build_match_card(leg: Dict[str, Any], all_block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gradi jedan "card" entry za btts.json, iz standardizovanog lega + all_data bloka (ako postoji).
    """
    fixture_id = leg.get("fixture_id")
    league_id = leg.get("league_id")
    league_name = leg.get("league_name")
    league_country = leg.get("league_country")
    home = leg.get("home")
    away = leg.get("away")
    kickoff = leg.get("kickoff")
    odds = leg.get("odds")

    fx = (all_block or {}).get("fixture") or {}
    league = fx.get("league") or {}
    teams = fx.get("teams") or {}

    # Override osnovnih polja ako su dostupna iz all_data
    if league.get("name"):
        league_name = league.get("name")
    if league.get("country"):
        league_country = league.get("country")

    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}

    card_id = f"BTTS-{fixture_id}"

    return {
        "card_id": card_id,
        "fixture_id": fixture_id,
        "league": {
            "id": league_id,
            "name": league_name,
            "country": league_country,
            "short": league.get("name") or league_name,
        },
        "kickoff": kickoff,
        "home": {
            "id": home_team.get("id"),
            "name": home_team.get("name") or home,
            "short": home_team.get("name") or home,
        },
        "away": {
            "id": away_team.get("id"),
            "name": away_team.get("name") or away,
            "short": away_team.get("name") or away,
        },
        "market": leg.get("market") or "BTTS_YES",
        "market_family": "BTTS",
        "pick_label": "Both Teams to Score – Yes",
        "odds": odds,
    }


def _build_stats_block(leg: Dict[str, Any], all_block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gradi bogati blok za btts.stats.json za jedan fixture.
    """
    fixture_id = leg.get("fixture_id")
    fx = (all_block or {}).get("fixture") or {}
    league = fx.get("league") or {}
    teams = fx.get("teams") or {}
    odds_block = (all_block or {}).get("odds") or {}
    h2h_last = (all_block or {}).get("h2h_last") or []

    home_stats = {
        "form": (all_block or {}).get("home_form"),
        "goals": (all_block or {}).get("home_goals"),
        "last5": (all_block or {}).get("home_last5"),
        "standings": (all_block or {}).get("home_standings"),
    }
    away_stats = {
        "form": (all_block or {}).get("away_form"),
        "goals": (all_block or {}).get("away_goals"),
        "last5": (all_block or {}).get("away_last5"),
        "standings": (all_block or {}).get("away_standings"),
    }

    # Basic metrike iz goals bloka (ako postoje)
    def _compute_avg_goals(goals_block: Dict[str, Any]) -> float:
        if not isinstance(goals_block, dict):
            return 0.0
        for_root = goals_block.get("for") or goals_block.get("scored") or {}
        avg = (for_root.get("average") or {}).get("total")
        try:
            return float(str(avg).replace(",", "."))
        except Exception:
            return 0.0

    home_avg_goals = _compute_avg_goals(home_stats.get("goals") or {})
    away_avg_goals = _compute_avg_goals(away_stats.get("goals") or {})

    # h2h agregati (BTTS rate, avg goals)
    h2h_btts_count = 0
    h2h_goals_sum = 0
    h2h_total = 0

    for row in h2h_last:
        try:
            goals = row.get("goals") or {}
            home_g = int(goals.get("home", 0))
            away_g = int(goals.get("away", 0))
        except Exception:
            continue
        h2h_total += 1
        total_g = home_g + away_g
        h2h_goals_sum += total_g
        if home_g > 0 and away_g > 0:
            h2h_btts_count += 1

    h2h_btts_rate = float(h2h_btts_count) / h2h_total if h2h_total else 0.0
    h2h_avg_goals = float(h2h_goals_sum) / h2h_total if h2h_total else 0.0

    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}

    return {
        "fixture": {
            "id": fx.get("id") or fixture_id,
            "date": fx.get("date") if isinstance(fx.get("date"), str) else None,
            "referee": fx.get("referee") if isinstance(fx.get("referee"), str) else None,
            "venue": fx.get("venue") or {},
        },
        "league": league,
        "teams": {
            "home": home_team,
            "away": away_team,
        },
        "odds": odds_block,
        "home": {
            **home_stats,
            "avg_goals": home_avg_goals,
        },
        "away": {
            **away_stats,
            "avg_goals": away_avg_goals,
        },
        "h2h": {
            "last_matches": h2h_last,
            "btts_rate": h2h_btts_rate,
            "avg_goals": h2h_avg_goals,
        },
    }


def build_btts_feed(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    all_data: Dict[Any, Any],
    day: date,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Glavna funkcija za jutarnji BTTS Yes feed.

    Ulaz:
      - fixtures: normalizovane fixtures za dan
      - odds: normalizovane odds za dan
      - all_data: rezultat build_all_data(...) ili učitan all_data.json
      - day: dan na koji se odnosi feed

    Izlaz:
      - (btts_feed, btts_stats) spremni za upis u public/btts*.json
    """
    print("[BTTS] Preparing BTTS Yes feed...")

    now_iso = datetime.utcnow().isoformat()

    if not fixtures or not odds:
        print("[BTTS] Empty fixtures or odds. Returning empty feed.")
        empty = {
            "date": day.isoformat(),
            "generated_at": now_iso,
            "meta": {
                "matches_count": 0,
                "leagues_count": 0,
                "odds_range": [BTTS_ODDS_MIN, BTTS_ODDS_MAX],
            },
            "matches": [],
        }
        return empty, {
            "date": day.isoformat(),
            "generated_at": now_iso,
            "fixtures": {},
        }

    # 1) Filtriraj fixtures na target lige
    fixtures_filtered = _filter_fixtures_by_leagues(fixtures)
    if not fixtures_filtered:
        print("[BTTS] No fixtures in BTTS leagues. Returning empty feed.")
        empty = {
            "date": day.isoformat(),
            "generated_at": now_iso,
            "meta": {
                "matches_count": 0,
                "leagues_count": 0,
                "odds_range": [BTTS_ODDS_MIN, BTTS_ODDS_MAX],
            },
            "matches": [],
        }
        return empty, {
            "date": day.isoformat(),
            "generated_at": now_iso,
            "fixtures": {},
        }

    # 2) Postojeći BTTS Yes builder nad filtriranim fixtures + kompletnim odds
    legs_all = build_btts_yes_legs(fixtures_filtered, odds, max_legs=500)
    print(f"[BTTS] Builder returned {len(legs_all)} candidate legs before odds filter.")

    # 3) Filter po kvoti
    legs_filtered: List[Dict[str, Any]] = []
    for leg in legs_all:
        try:
            o = float(leg.get("odds"))
        except (TypeError, ValueError):
            continue
        if BTTS_ODDS_MIN <= o <= BTTS_ODDS_MAX:
            legs_filtered.append(leg)

    print(f"[BTTS] {len(legs_filtered)} legs after odds filter {BTTS_ODDS_MIN}-{BTTS_ODDS_MAX}.")

    # Sortiranje po kickoff (ISO) pa po kvoti rastuće
    legs_sorted = sorted(
        legs_filtered,
        key=lambda x: (x.get("kickoff") or "", float(x.get("odds") or 0.0)),
    )

    all_index = _index_all_data(all_data)

    matches_cards: List[Dict[str, Any]] = []
    fixtures_stats: Dict[str, Dict[str, Any]] = {}

    for leg in legs_sorted:
        fid = leg.get("fixture_id")
        if fid is None:
            continue
        fid_int = int(fid)
        block = all_index.get(fid_int, {})

        card = _build_match_card(leg, block)
        stats_block = _build_stats_block(leg, block)

        matches_cards.append(card)
        fixtures_stats[str(fid_int)] = stats_block

    leagues_ids = sorted(
        {
            m["league"]["id"]
            for m in matches_cards
            if isinstance(m.get("league", {}).get("id"), int)
        }
    )

    btts_feed = {
        "date": day.isoformat(),
        "generated_at": now_iso,
        "meta": {
            "matches_count": len(matches_cards),
            "leagues_count": len(leagues_ids),
            "leagues": leagues_ids,
            "odds_range": [BTTS_ODDS_MIN, BTTS_ODDS_MAX],
        },
        "matches": matches_cards,
    }

    btts_stats = {
        "date": day.isoformat(),
        "generated_at": now_iso,
        "fixtures": fixtures_stats,
    }

    print(
        f"[BTTS] Feed ready: matches={len(matches_cards)}, "
        f"leagues={len(leagues_ids)}, date={day.isoformat()}"
    )

    return btts_feed, btts_stats
