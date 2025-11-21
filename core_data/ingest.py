import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from .api_client import (
    fetch_fixtures_by_date,
    fetch_odds_by_date,
    fetch_standings,
    fetch_team_stats,
    fetch_h2h,
    get_api_status,
)
from .cache import write_json, read_json, cache_status
from .cleaners import (
    clean_fixtures,
    clean_odds,
    clean_standings,
    clean_team_stats,
    clean_h2h,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Konfiguracija liga i rizika
# ---------------------------------------------------------------------

# Default allow liste liga – možeš da ih prilagodiš.
DEFAULT_LEAGUES: List[int] = [2,3,913,5,536,808,960,10,667,29,30,31,32,37,33,34,848,311,310,342,218,144,315,71,
    169,210,346,233,39,40,41,42,703,244,245,61,62,78,79,197,271,164,323,135,136,389,
    88,89,408,103,104,106,94,283,235,286,287,322,140,141,113,207,208,202,203,909,268,269,270,340
    39,   # Premier League
    140,  # La Liga
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    88,   # Eredivisie
    201,  # Super Liga Srbije (primer)
    2,    # Champions League
    3,    # Europa League
    848,  # Conference League
]

# Mape liga -> sezona (API-FOOTBALL zahteva season param)
SEASON_MAP: Dict[int, int] = {
    39: 2024,
    140: 2024,
    135: 2024,
    78: 2024,
    61: 2024,
    88: 2024,
    201: 2024,
    2: 2024,
    3: 2024,
    848: 2024,
}

# Lige koje želiš da izbegneš (rizik, slaba pouzdanost, itd.)
RISKY_LEAGUES: List[int] = [
    291,  # Iran Azadegan League (primer)
    292,  # Iran Persian Gulf Pro League (primer)
    299,  # UAE Pro League (primer)
]


# ---------------------------------------------------------------------
# Helperi
# ---------------------------------------------------------------------


def _date_str(d: date) -> str:
    return d.isoformat()


def _daterange(start_day: date, days_ahead: int) -> List[date]:
    return [start_day + timedelta(days=i) for i in range(days_ahead + 1)]


def _filter_risky_leagues(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Izbaci fixture-e iz liga koje su u RISKY_LEAGUES.
    """

    if not fixtures:
        return fixtures

    filtered: List[Dict[str, Any]] = []
    dropped = 0

    for fx in fixtures:
        league = fx.get("league") or {}
        league_id = league.get("id")
        if league_id in RISKY_LEAGUES:
            dropped += 1
            continue
        filtered.append(fx)

    if dropped:
        logger.info("[INGEST] Dropped %s fixtures from risky leagues.", dropped)

    return filtered


def _summarize_items(label: str, raw: Any) -> List[Dict[str, Any]]:
    """
    Helper koji proverava format sirovog responsa i vadi listu dict-ova.
    Ovo je defensive logika jer API-FOOTBALL uglavnom vraća:
        {"response": [ {...}, {...} ]}
    ali može da bude i direktna lista ili nešto treće.
    """

    items: List[Dict[str, Any]] = []

    if raw is None:
        logger.warning("[INGEST] %s returned None.", label)
        return items

    if isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
        print(f"[DEBUG] {label}: raw list with {len(items)} dict items.")
        return items

    if isinstance(raw, dict):
        # API-FOOTBALL stil: {"response": [...]}
        if "response" in raw and isinstance(raw["response"], list):
            items = [x for x in raw["response"] if isinstance(x, dict)]
            print(f"[DEBUG] {label}: dict with response[{len(items)}].")
            return items

        # već očišćena lista u nekom polju
        for key in ("items", "data", "rows"):
            val = raw.get(key)
            if isinstance(val, list):
                items = [x for x in val if isinstance(x, dict)]
                print(f"[DEBUG] {label}: dict with {key}[{len(items)}].")
                return items

    logger.warning("[INGEST] %s: unsupported raw type %s", label, type(raw))
    return items


# ---------------------------------------------------------------------
# Glavni ingest
# ---------------------------------------------------------------------


def fetch_all_data(days_ahead: int = 2) -> Dict[str, Any]:
    """
    Centralni dnevni job za ingest (07:00 run):

    - fixtures + odds za danas + naredna 2 dana
    - standings za sve DEFAULT_LEAGUES (samo za danas)
    - team stats za timove iz današnjih fixtures
    - h2h(last=5) za sve današnje mečeve

    Sve se upisuje u:
    /cache/YYYY-MM-DD/fixtures.json
    /cache/YYYY-MM-DD/odds.json
    /cache/YYYY-MM-DD/standings/<league>.json
    /cache/YYYY-MM-DD/stats/<league>_<team>.json
    /cache/YYYY-MM-DD/h2h/<fixture>.json

    Vraća summary dict za dalje logovanje.
    """

    today = date.today()
    days = _daterange(today, days_ahead=days_ahead)

    logger.info("[INGEST] fetch_all_data start: today=%s, days_ahead=%s", today, days_ahead)

    # Aggregated counters za summary
    fixtures_total = 0
    odds_total = 0
    standings_total = 0
    stats_total = 0
    h2h_total = 0

    # Beležimo i današnji fixtures odvojeno (za stats/h2h)
    fixtures_today: List[Dict[str, Any]] = []

    # Summary per-day
    results_summary: Dict[str, Any] = {
        "fixtures_days": [],
        "odds_days": [],
        "standings_leagues": [],
        "stats_entries": [],
        "h2h_entries": [],
    }

    # -------------------------
    # 1) Fixtures + Odds po danima
    # -------------------------
    for d in days:
        ds = _date_str(d)

        # 1.1 Fixtures
        raw_fixtures = fetch_fixtures_by_date(ds)
        fixtures = clean_fixtures(raw_fixtures)
        fixtures = _filter_risky_leagues(fixtures)
        write_json("fixtures.json", fixtures, day=d)
        results_summary["fixtures_days"].append({"date": ds, "count": len(fixtures)})
        logger.info("[INGEST] Fixtures loaded for %s: count=%s", ds, len(fixtures))

        # === DEBUG: distribucija liga i sample mečeva po datumu ===
        if fixtures:
            league_counts: Dict[str, int] = {}
            sample_fixtures: List[Dict[str, Any]] = []

            for fx in fixtures:
                league = fx.get("league") or {}
                teams = fx.get("teams") or {}
                fixture_meta = fx.get("fixture") or {}

                lid = league.get("id")
                lname = league.get("name")
                lcountry = league.get("country")

                key = f"{lcountry} | {lname} ({lid})"
                league_counts[key] = league_counts.get(key, 0) + 1

                if len(sample_fixtures) < 15:
                    sample_fixtures.append(
                        {
                            "fixture_id": fixture_meta.get("id"),
                            "league": key,
                            "kickoff": fixture_meta.get("date"),
                            "home": (teams.get("home") or {}).get("name"),
                            "away": (teams.get("away") or {}).get("name"),
                        }
                    )

            logger.debug(
                "[INGEST][DEBUG] Fixtures league distribution for %s: %s",
                ds,
                "; ".join(f"{k} -> {v}" for k, v in sorted(league_counts.items())),
            )
            logger.debug(
                "[INGEST][DEBUG] Fixtures sample for %s: %s",
                ds,
                json.dumps(sample_fixtures, ensure_ascii=False),
            )

        if d == today:
            fixtures_today = fixtures

        # 1.2 Odds
        raw_odds = fetch_odds_by_date(ds)
        odds = clean_odds(raw_odds)
        write_json("odds.json", odds, day=d)
        results_summary["odds_days"].append({"date": ds, "count": len(odds)})
        logger.info("[INGEST] Odds loaded for %s: count=%s", ds, len(odds))

        # === DEBUG: distribucija liga u odds ===
        if odds:
            odds_by_league: Dict[int, int] = {}
            for row in odds:
                lid = row.get("league_id")
                if isinstance(lid, int):
                    odds_by_league[lid] = odds_by_league.get(lid, 0) + 1

            label_lines: List[str] = []
            for lid, cnt in sorted(odds_by_league.items()):
                league_label = None
                # probaj da pronađeš opis lige u fixtures za isti dan
                for fx in fixtures:
                    league = fx.get("league") or {}
                    if league.get("id") == lid:
                        league_label = f"{league.get('country')} | {league.get('name')} ({lid})"
                        break
                if not league_label:
                    league_label = f"league_id={lid}"

                label_lines.append(f"{league_label}: odds={cnt}")

            logger.debug(
                "[INGEST][DEBUG] Odds league distribution for %s: %s",
                ds,
                "; ".join(label_lines),
            )

    # Ako iz nekog razloga danas nema fixtures, probaj fallback iz keša
    if not fixtures_today:
        cached_fixtures = read_json("fixtures.json", day=today)
        if isinstance(cached_fixtures, list):
            fixtures_today = cached_fixtures
            logger.warning("[INGEST] No fresh fixtures for today, using cached fixtures for %s", today_str)

    # 2) STANDINGS za sve DEFAULT_LEAGUES
    for league_id in DEFAULT_LEAGUES:
        season = SEASON_MAP.get(league_id)
        if not season:
            logger.warning("[INGEST] No SEASON_MAP entry for league_id=%s, skipping standings", league_id)
            continue

        raw_standings = fetch_standings(league_id=league_id, season=season)
        standings = clean_standings(raw_standings)
        write_json(f"standings_{league_id}.json", standings, day=today)
        results_summary["standings_leagues"].append(
            {"league_id": league_id, "season": season, "rows": len(standings)}
        )
        logger.info(
            "[INGEST] Standings loaded for league_id=%s season=%s: rows=%s",
            league_id,
            season,
            len(standings),
        )

    # 3) Team stats za timove iz današnjih fixtures
    team_stats_counter = 0
    seen_teams: Dict[str, bool] = {}

    for fx in fixtures_today:
        league = fx.get("league") or {}
        fixture = fx.get("fixture") or {}
        teams = fx.get("teams") or {}

        league_id = league.get("id")
        season = SEASON_MAP.get(league_id)
        if not season:
            continue

        for side in ("home", "away"):
            tinfo = (teams.get(side) or {})
            team_id = tinfo.get("id")
            if not team_id:
                continue

            key = f"{league_id}_{team_id}"
            if seen_teams.get(key):
                continue

            raw_stats = fetch_team_stats(league_id=league_id, season=season, team_id=team_id)
            stats = clean_team_stats(raw_stats)
            write_json(f"stats_{league_id}_{team_id}.json", stats, day=today)
            seen_teams[key] = True
            team_stats_counter += 1

    results_summary["stats_entries"].append(
        {
            "date": today.isoformat(),
            "teams": len(seen_teams),
            "files": team_stats_counter,
        }
    )
    logger.info("[INGEST] Team stats entries written: teams=%s, files=%s", len(seen_teams), team_stats_counter)

    # 4) H2H(last=5) za sve današnje mečeve
    h2h_counter = 0
    for fx in fixtures_today:
        fixture = fx.get("fixture") or {}
        teams = fx.get("teams") or {}

        fixture_id = fixture.get("id")
        home = (teams.get("home") or {}).get("id")
        away = (teams.get("away") or {}).get("id")
        if not fixture_id or not home or not away:
            continue

        raw_h2h = fetch_h2h(home=home, away=away, last=5)
        h2h = clean_h2h(raw_h2h)
        write_json(f"h2h_{fixture_id}.json", h2h, day=today)
        h2h_counter += 1

    results_summary["h2h_entries"].append(
        {
            "date": today.isoformat(),
            "fixtures": len(fixtures_today),
            "files": h2h_counter,
        }
    )
    logger.info("[INGEST] H2H entries written: fixtures=%s, files=%s", len(fixtures_today), h2h_counter)

    # Aggregated totals
    fixtures_total = sum(x["count"] for x in results_summary["fixtures_days"])
    odds_total = sum(x["count"] for x in results_summary["odds_days"])
    standings_total = sum(x["rows"] for x in results_summary["standings_leagues"])
    stats_total = sum(x["files"] for x in results_summary["stats_entries"])
    h2h_total = sum(x["files"] for x in results_summary["h2h_entries"])

    summary = {
        "today": today.isoformat(),
        "days_ahead": days_ahead,
        "fixtures_total": fixtures_total,
        "odds_total": odds_total,
        "standings_total": standings_total,
        "stats_total": stats_total,
        "h2h_total": h2h_total,
        "fixtures_days": results_summary["fixtures_days"],
        "odds_days": results_summary["odds_days"],
        "standings_leagues": results_summary["standings_leagues"],
        "stats_entries": results_summary["stats_entries"],
        "h2h_entries": results_summary["h2h_entries"],
        # placeholder za AI min_score: kasnije se popunjava u morning_run
        "min_score": None,
        "raw_sets": None,
        "raw_total_tickets": None,
    }

    logger.info(
        "[INGEST] Summary: fixtures_total=%s, odds_total=%s, standings_total=%s, stats_total=%s, h2h_total=%s",
        fixtures_total,
        odds_total,
        standings_total,
        stats_total,
        h2h_total,
    )

    # all_data.json je opcioni agregat koji može da sadrži
    # referencu na sve gore navedeno (ako želiš)
    all_data = {
        "fixtures_today": fixtures_today,
        "fixtures_days": results_summary["fixtures_days"],
        "odds_days": results_summary["odds_days"],
        "standings_leagues": results_summary["standings_leagues"],
        "stats_entries": results_summary["stats_entries"],
        "h2h_entries": results_summary["h2h_entries"],
    }
    write_json("all_data.json", all_data, day=today)

    return summary


# ---------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------


def check_data_readiness(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Jednostavan readiness check koji možeš da pozoveš posle ingest-a
    ili iz health endpointa.

    Gleda da li postoje keš fajlovi za zadati dan
    i vraća status OK / WARNING / ERROR.
    """
    d = target_date or date.today()

    cache_info = cache_status(day=d)

    status = "OK"
    messages: List[str] = []

    if cache_info.get("missing_files"):
        status = "WARNING"
        messages.append(f"Missing files: {', '.join(cache_info['missing_files'])}")

    if cache_info.get("stale_files"):
        if status == "OK":
            status = "WARNING"
        messages.append(f"Stale files: {', '.join(cache_info['stale_files'])}")

    return {
        "date": d.isoformat(),
        "status": status,
        "details": messages,
        "cache": cache_info,
    }


def run_morning_ingest_and_check() -> None:
    """
    Helper koji:
    - pokreće fetch_all_data()
    - odmah radi check_data_readiness()
    - printa sve u JSON formatu (korisno za debug/CLI)
    """
    summary = fetch_all_data(days_ahead=2)
    readiness = check_data_readiness()

    output = {
        "summary": summary,
        "readiness": readiness,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # Omogući basic logging kada direktno startuješ skriptu
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_morning_ingest_and_check()
