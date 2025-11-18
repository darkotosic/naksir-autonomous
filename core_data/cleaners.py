from typing import Any, Dict, List, Optional, Union

# Globalni range za "validne" kvote u ingest sloju
ALLOWED_ODDS_MIN = 1.08
ALLOWED_ODDS_MAX = 1.45


# -----------------------------
# Helper funkcije
# -----------------------------

def _as_list(raw: Any) -> List[Any]:
    """
    API-FOOTBALL obično vraća dict sa 'response' listom.
    Ovo normalizuje na listu.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("response", []) or []
    return []


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


# -----------------------------
# FIXTURES
# -----------------------------

def clean_fixtures(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalizuje API-FOOTBALL fixtures rezultat na stabilan, trimmed format.
    Zadržava glavne segmente: fixture, league, teams, goals, score.
    """
    fixtures_clean: List[Dict[str, Any]] = []

    for item in _as_list(raw):
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        score = item.get("score") or {}

        # Osnovne validacije
        fid = _safe_int(fixture.get("id"))
        lid = _safe_int(league.get("id"))
        season = _safe_int(league.get("season"))

        home = teams.get("home") or {}
        away = teams.get("away") or {}
        home_id = _safe_int(home.get("id"))
        away_id = _safe_int(away.get("id"))

        if not fid or not lid or not home_id or not away_id:
            # Ako nema osnovne identifikacije, preskačemo fixture
            continue

        clean_item = {
            "fixture": {
                "id": fid,
                "referee": fixture.get("referee"),
                "timezone": fixture.get("timezone"),
                "date": fixture.get("date"),
                "timestamp": _safe_int(fixture.get("timestamp")),
                "periods": fixture.get("periods") or {},
                "venue": {
                    "id": _safe_int((fixture.get("venue") or {}).get("id")),
                    "name": (fixture.get("venue") or {}).get("name"),
                    "city": (fixture.get("venue") or {}).get("city"),
                },
                "status": {
                    "long": (fixture.get("status") or {}).get("long"),
                    "short": (fixture.get("status") or {}).get("short"),
                    "elapsed": _safe_int((fixture.get("status") or {}).get("elapsed")),
                },
            },
            "league": {
                "id": lid,
                "name": league.get("name"),
                "country": league.get("country"),
                "logo": league.get("logo"),
                "flag": league.get("flag"),
                "season": season,
                "round": league.get("round"),
            },
            "teams": {
                "home": {
                    "id": home_id,
                    "name": home.get("name"),
                    "logo": home.get("logo"),
                    "winner": home.get("winner"),
                },
                "away": {
                    "id": away_id,
                    "name": away.get("name"),
                    "logo": away.get("logo"),
                    "winner": away.get("winner"),
                },
            },
            "goals": {
                "home": _safe_int(goals.get("home")),
                "away": _safe_int(goals.get("away")),
            },
            "score": score or {},
        }

        fixtures_clean.append(clean_item)

    return fixtures_clean


# -----------------------------
# ODDS
# -----------------------------

def clean_odds(raw: Any) -> List[Dict[str, Any]]:
    """
    Flatten + očisti API-FOOTBALL odds.
    Vraća listu pojedinačnih kvota sa osnovnim kontekstom.

    Struktura elementa:
    {
        "fixture_id": int,
        "league_id": int,
        "bookmaker_id": int,
        "bookmaker_name": str,
        "bet_id": int,
        "bet_name": str,
        "label": str,     # npr. "Home", "Over 2.5", "Yes"
        "odd": float,
        "updated_at": str
    }
    """
    odds_clean: List[Dict[str, Any]] = []

    for item in _as_list(raw):
        fixture = item.get("fixture") or {}
        league = item.get("league") or {}
        bookmakers = item.get("bookmakers") or []

        fid = _safe_int(fixture.get("id"))
        lid = _safe_int(league.get("id"))
        updated_at = item.get("update")

        if not fid or not lid:
            continue

        for bm in bookmakers:
            bm_id = _safe_int(bm.get("id"))
            bm_name = bm.get("name") or "Unknown"
            bets = bm.get("bets") or []

            for bet in bets:
                bet_id = _safe_int(bet.get("id"))
                bet_name = bet.get("name") or "Unknown bet"
                values = bet.get("values") or []

                for v in values:
                    label = v.get("value") or ""   # npr. "Home", "Away", "Over 2.5"
                    odd_val = _safe_float(v.get("odd"))

                    # Filterišemo invalidne ili van-range kvote
                    if odd_val is None:
                        continue
                    if odd_val < ALLOWED_ODDS_MIN or odd_val > ALLOWED_ODDS_MAX:
                        # I dalje možemo da ih sačuvamo za debug ako želiš,
                        # ali za core sistem filtriramo out-of-range
                        continue

                    odds_clean.append(
                        {
                            "fixture_id": fid,
                            "league_id": lid,
                            "bookmaker_id": bm_id,
                            "bookmaker_name": bm_name,
                            "bet_id": bet_id,
                            "bet_name": bet_name,
                            "label": label,
                            "odd": odd_val,
                            "updated_at": updated_at,
                        }
                    )

    return odds_clean


# -----------------------------
# STANDINGS
# -----------------------------

def clean_standings(raw: Any) -> List[Dict[str, Any]]:
    """
    Čisti standings u ravnu listu per-team.

    Struktura:
    {
        "league_id": int,
        "season": int,
        "team_id": int,
        "team_name": str,
        "rank": int,
        "points": int,
        "played": int,
        "win": int,
        "draw": int,
        "lose": int,
        "goals_for": int,
        "goals_against": int,
        "goals_diff": int,
        "form": str
    }
    """
    rows: List[Dict[str, Any]] = []

    for item in _as_list(raw):
        league = item.get("league") or {}
        lid = _safe_int(league.get("id"))
        season = _safe_int(league.get("season"))
        standings = (league.get("standings") or [])

        # standings je obično lista lista ([[team1, team2,...]])
        for grp in standings:
            for row in grp:
                team = row.get("team") or {}
                all_stats = row.get("all") or {}
                goals = all_stats.get("goals") or {}

                team_id = _safe_int(team.get("id"))
                if not lid or not team_id:
                    continue

                rows.append(
                    {
                        "league_id": lid,
                        "season": season,
                        "team_id": team_id,
                        "team_name": team.get("name"),
                        "rank": _safe_int(row.get("rank")),
                        "points": _safe_int(row.get("points")),
                        "played": _safe_int(all_stats.get("played")),
                        "win": _safe_int(all_stats.get("win")),
                        "draw": _safe_int(all_stats.get("draw")),
                        "lose": _safe_int(all_stats.get("lose")),
                        "goals_for": _safe_int(goals.get("for")),
                        "goals_against": _safe_int(goals.get("against")),
                        "goals_diff": _safe_int(row.get("goalsDiff")),
                        "form": row.get("form"),
                    }
                )

    return rows


# -----------------------------
# TEAM STATS
# -----------------------------

def clean_team_stats(raw: Any) -> Dict[str, Any]:
    """
    Čisti team statistics endpoint u kompaktan format fokusiran na ključne metrike
    koje su potrebne za AI i buildere.

    Vraća dict:
    {
        "team_id": int,
        "league_id": int,
        "season": int,
        "form": str,
        "fixtures": { ... },
        "goals": { ... },
        "shots": { ... },
        "cards": { ... }
        ...
    }

    Napomena: Ostavlja nested strukturu ali filtrira na najbitnije delove.
    """
    # API-FOOTBALL vraća jedan objekat u response listi
    items = _as_list(raw)
    if not items:
        return {}

    item = items[0]

    team = item.get("team") or {}
    league = item.get("league") or {}

    fixtures = item.get("fixtures") or {}
    goals = item.get("goals") or {}
    shots = item.get("shots") or {}
    cards = item.get("cards") or {}
    lineups = item.get("lineups") or {}
    form = item.get("form")

    clean_stats = {
        "team_id": _safe_int(team.get("id")),
        "team_name": team.get("name"),
        "league_id": _safe_int(league.get("id")),
        "league_name": league.get("name"),
        "season": _safe_int(league.get("season")),
        "form": form,
        "fixtures": fixtures,
        "goals": goals,
        "shots": shots,
        "cards": cards,
        "lineups": lineups,
    }

    return clean_stats


# -----------------------------
# H2H
# -----------------------------

def clean_h2h(raw: Any) -> List[Dict[str, Any]]:
    """
    H2H endpoint obično vraća listu fixtures-ova (mečeva između dva tima).
    Ovde jednostavno koristimo clean_fixtures ali ga tretiramo kao H2H set.
    """
    return clean_fixtures(raw)
