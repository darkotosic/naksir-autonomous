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

# TODO: prebaci po potrebi u posebni leagues.py modul
# Primer allow lista (top evropske lige)
DEFAULT_LEAGUES: List[int] = [
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
    
    # dodaj po potrebi: 78 (Bundesliga), 61 (Ligue 1), itd.
]

# Mapiranje liga -> sezona (OBAVEZNO prilagodi aktuelnoj sezoni)
SEASON_MAP: Dict[int, int] = {
    39: 2024,
    140: 2024,
    135: 2024,
    # 78: 2024,
    # 61: 2024,
}

# Lige koje želiš da tretiraš kao rizične (npr. Iran, UAE, egzotične)
RISKY_LEAGUES: List[int] = [
    # primer: 751, 752
]


# ---------------------------------------------------------------------
# Helper funkcije
# ---------------------------------------------------------------------

def _date_str(d: Optional[date] = None) -> str:
    return (d or date.today()).isoformat()


def get_dates_window(days_ahead: int = 2) -> List[date]:
    """
    Vraća listu datuma: danas + narednih X dana.
    Koristi se za fixtures/odds ingest prozor.
    """
    today = date.today()
    return [today + timedelta(days=i) for i in range(days_ahead + 1)]


# ---------------------------------------------------------------------
# LAYER 1 – Data Automation: fetch_all_data
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
    """

    today = date.today()
    today_str = _date_str(today)

    logger.info("[INGEST] Starting fetch_all_data for date=%s, days_ahead=%s", today_str, days_ahead)

    results_summary: Dict[str, Any] = {
        "fixtures_days": [],
        "odds_days": [],
        "standings": [],
        "team_stats": [],
        "h2h_fixtures": [],
    }

    # 1) FIXTURES + ODDS za danas + naredna 2 dana
    fixtures_today: List[Dict[str, Any]] = []

    for d in get_dates_window(days_ahead=days_ahead):
        ds = _date_str(d)

        # 1.1 Fixtures
        raw_fixtures = fetch_fixtures_by_date(ds)
        fixtures = clean_fixtures(raw_fixtures)
        write_json("fixtures.json", fixtures, day=d)
        results_summary["fixtures_days"].append({"date": ds, "count": len(fixtures)})
        logger.info("[INGEST] Fixtures loaded for %s: count=%s", ds, len(fixtures))

        if d == today:
            fixtures_today = fixtures

        # 1.2 Odds
        raw_odds = fetch_odds_by_date(ds)
        odds = clean_odds(raw_odds)
        write_json("odds.json", odds, day=d)
        results_summary["odds_days"].append({"date": ds, "count": len(odds)})
        logger.info("[INGEST] Odds loaded for %s: count=%s", ds, len(odds))

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
        write_json(f"standings/{league_id}.json", standings, day=today)
        results_summary["standings"].append({"league": league_id, "teams": len(standings)})
        logger.info("[INGEST] Standings loaded for league=%s season=%s: teams=%s", league_id, season, len(standings))

    # 3) TEAM STATS – za timove koji se pojavljuju u današnjim fixtures
    team_ids_by_league: Dict[int, set[int]] = {}

    for fx in fixtures_today:
        league = fx.get("league") or {}
        lid = league.get("id")
        if lid not in DEFAULT_LEAGUES:
            continue

        teams = fx.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        home_id = home.get("id")
        away_id = away.get("id")

        if not home_id or not away_id:
            continue

        team_ids_by_league.setdefault(lid, set()).update({home_id, away_id})

    for league_id, team_ids in team_ids_by_league.items():
        season = SEASON_MAP.get(league_id)
        if not season:
            logger.warning("[INGEST] No SEASON_MAP entry for league_id=%s, skipping team stats", league_id)
            continue

        for team_id in sorted(team_ids):
            raw_stats = fetch_team_stats(league_id=league_id, season=season, team_id=team_id)
            stats = clean_team_stats(raw_stats)
            write_json(f"stats/{league_id}_{team_id}.json", stats, day=today)
            results_summary["team_stats"].append(
                {"league": league_id, "team_id": team_id}
            )
        logger.info(
            "[INGEST] Team stats loaded for league=%s season=%s teams=%s",
            league_id,
            season,
            len(team_ids),
        )

    # 4) H2H (last=5) za sve današnje mečeve
    h2h_count = 0
    for fx in fixtures_today:
        fixture = fx.get("fixture") or {}
        teams = fx.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}

        fixture_id = fixture.get("id")
        home_id = home.get("id")
        away_id = away.get("id")

        if not fixture_id or not home_id or not away_id:
            continue

        raw_h2h = fetch_h2h(home_id=home_id, away_id=away_id, last=5)
        h2h = clean_h2h(raw_h2h)
        write_json(f"h2h/{fixture_id}.json", h2h, day=today)
        h2h_count += 1

    results_summary["h2h_fixtures"].append({"date": today_str, "count": h2h_count})
    logger.info("[INGEST] H2H loaded for today=%s: fixtures=%s", today_str, h2h_count)

    logger.info("[INGEST] fetch_all_data completed for %s", today_str)
    return results_summary


# ---------------------------------------------------------------------
# 07:00 Morning Data Readiness Check
# ---------------------------------------------------------------------

def check_data_readiness(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    07:00 Morning Data Readiness Checklist u kodu.

    Proverava:
    - API status i rate limit
    - Da li postoje fixtures/odds/standings fajlovi za target_date
    - Osnovnu validaciju: null polja, rizične lige, invalid odds

    Vraća:
    {
      "ok": bool,
      "errors": [...],
      "warnings": [...],
      "stats": {...},
      "cache": {...}  # snapshot strukture
    }
    """
    if target_date is None:
        target_date = date.today()

    ds = _date_str(target_date)
    errors: List[str] = []
    warnings: List[str] = []
    stats: Dict[str, Any] = {}

    logger.info("[CHECK] Data readiness check for %s", ds)

    # 1) API health
    api_status = get_api_status()
    if not api_status["ok"]:
        errors.append("API-Football status NOT OK")
        logger.error("[CHECK] API status NOT OK")

    rl = api_status.get("rate_limit") or {}
    try:
        limit = int(rl.get("x-ratelimit-requests-limit") or 0)
        remaining = int(rl.get("x-ratelimit-requests-remaining") or 0)
        if limit > 0:
            used_pct = (limit - remaining) / limit * 100
            stats["rate_limit_used_pct"] = used_pct
            if used_pct > 85:
                warnings.append(f"API rate limit usage high: {used_pct:.1f}%")
                logger.warning("[CHECK] Rate limit high: used=%.1f%%", used_pct)
    except ValueError:
        warnings.append("Cannot parse rate limit headers")
        logger.warning("[CHECK] Cannot parse rate limit headers: %s", rl)

    # 2) Data ingestion – da li fajlovi postoje i osnovne brojke
    fixtures = read_json("fixtures.json", day=target_date)
    odds = read_json("odds.json", day=target_date)

    if not fixtures:
        errors.append("Missing or empty fixtures.json")
        logger.error("[CHECK] Missing or empty fixtures.json for %s", ds)
    if not odds:
        errors.append("Missing or empty odds.json")
        logger.error("[CHECK] Missing or empty odds.json for %s", ds)

    stats["fixtures_count"] = len(fixtures or [])
    stats["odds_count"] = len(odds or [])

    # Proveri da li postoji barem jedan standings fajl
    has_standings = False
    for league_id in DEFAULT_LEAGUES:
        st = read_json(f"standings/{league_id}.json", day=target_date)
        if st:
            has_standings = True
            break

    if not has_standings:
        warnings.append("Standings not loaded for default leagues (check cron)")
        logger.warning("[CHECK] Standings missing for default leagues on %s", ds)

    # 3) Data validation – null polja, rizične lige, invalid odds range
    # 3.1 Fixtures validacija
    if fixtures:
        risky_leagues_found = set()
        for fx in fixtures:
            fixture = fx.get("fixture") or {}
            league = fx.get("league") or {}
            teams = fx.get("teams") or {}

            if not fixture or not league or not teams:
                errors.append("Fixture with missing basic fields detected")
                logger.error("[CHECK] Fixture with missing basic fields detected")
                break

            league_id = league.get("id")
            if league_id in RISKY_LEAGUES:
                risky_leagues_found.add(league_id)

            if not fixture.get("date"):
                errors.append("Fixture without date detected")
                logger.error("[CHECK] Fixture without date detected")
                break

        if risky_leagues_found:
            warnings.append(f"Risk leagues present in fixtures: {sorted(risky_leagues_found)}")
            logger.warning(
                "[CHECK] Risk leagues present in fixtures: %s",
                sorted(risky_leagues_found),
            )

    # 3.2 Odds validacija – ovde ne proveravamo range, jer clean_odds ga već filtrira.
    # Ali proverimo da li ima nečega; ako je count=0, to je problem.
    if odds and len(odds) == 0:
        warnings.append("Odds list exists but has 0 entries")

    # 4) Cache snapshot (diagnostic)
    cache_info = cache_status(day=target_date)

    ok = len(errors) == 0
    result = {
        "ok": ok,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "cache": cache_info,
    }

    logger.info("[CHECK] Data readiness result for %s: ok=%s", ds, ok)
    if errors:
        logger.error("[CHECK] Errors: %s", errors)
    if warnings:
        logger.warning("[CHECK] Warnings: %s", warnings)

    return result


# ---------------------------------------------------------------------
# CLI / GitHub Actions entrypoint
# ---------------------------------------------------------------------

def run_morning_ingest_and_check() -> None:
    """
    Helper koji koristiš u GitHub Actions (07:00 job):

    - pokreće fetch_all_data()
    - pokreće check_data_readiness()
    - printa JSON summary na stdout (da vidiš sve u logu)
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
