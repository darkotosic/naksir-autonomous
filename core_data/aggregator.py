"""
Aggregation layer for Naksir Autonomous:
build_all_data() combines fixtures, odds, standings, team_stats and h2h
into a single per-fixture dataset (all_data.json).
"""

from __future__ import annotations

from typing import Any, Dict, List

def _index_fixtures(fixtures: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for fx in fixtures:
        try:
            fid = fx.get("fixture", {}).get("id")
        except AttributeError:
            fid = None
        if fid is None:
            continue
        if not isinstance(fid, int):
            try:
                fid = int(fid)
            except Exception:
                continue
        out[fid] = fx
    return out


def _index_odds(odds: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = {}
    for row in odds:
        try:
            fid = row.get("fixture", {}).get("id")
        except AttributeError:
            fid = None
        if fid is None:
            continue
        if not isinstance(fid, int):
            try:
                fid = int(fid)
            except Exception:
                continue
        out.setdefault(fid, []).append(row)
    return out


def _index_team_stats(team_stats: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    out: Dict[tuple, Dict[str, Any]] = {}
    for row in team_stats:
        league_id = row.get("league")
        team_id = row.get("team_id") or row.get("team", {}).get("id")
        if league_id is None or team_id is None:
            continue
        out[(league_id, team_id)] = row
    return out


def _index_standings(standings_data: List[Dict[str, Any]]) -> Dict[int, Dict[int, Dict[str, Any]]]:
    """
    standings_data format (per-league) is expected to be whatever cache stored.
    We normalise to: league_id -> team_id -> row.
    """
    out: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for block in standings_data:
        league_id = block.get("league") or block.get("league_id")
        if league_id is None:
            continue

        teams = []
        # API-FOOTBALL native: {"response":[{"league":{...,"standings":[[...]]}}]}
        if "standings" in block:
            # Already reduced structure
            teams = block.get("teams") or block.get("standings") or []
        elif "response" in block and isinstance(block["response"], list):
            # Try to unwrap original API structure if still present
            for item in block["response"]:
                league = item.get("league") or {}
                sts = league.get("standings") or []
                # "standings" is usually list-of-lists
                if sts and isinstance(sts[0], list):
                    for row in sts[0]:
                        teams.append(row)

        team_map: Dict[int, Dict[str, Any]] = {}
        for row in teams:
            team = row.get("team") or {}
            team_id = row.get("team_id") or team.get("id")
            if team_id is None:
                continue
            team_map[team_id] = row

        if team_map:
            out[league_id] = team_map

    return out


def _index_h2h(h2h_list: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """
    h2h_list is expected to be a list of API-FOOTBALL H2H payloads.
    We keep them grouped by current fixture_id where possible.
    """
    out: Dict[int, List[Dict[str, Any]]] = {}
    for block in h2h_list:
        # Two possible cache shapes:
        #   {"response":[{fixture:{id:..}, ...}, ...]}
        #   {"fixture_id": 123, "matches":[...]}
        if "response" in block and isinstance(block["response"], list):
            for m in block["response"]:
                fid = (m.get("fixture") or {}).get("id")
                if fid is None:
                    continue
                out.setdefault(fid, []).append(m)
        elif "fixture_id" in block:
            fid = block.get("fixture_id")
            matches = block.get("matches") or block.get("data") or []
            if fid is None:
                continue
            for m in matches:
                out.setdefault(fid, []).append(m)
    return out


def _extract_form(stats_row: Dict[str, Any]) -> str:
    if not stats_row:
        return ""
    return stats_row.get("form") or ""


def _extract_goals_block(stats_row: Dict[str, Any]) -> Dict[str, Any]:
    if not stats_row:
        return {}
    goals = stats_row.get("goals")
    return goals if isinstance(goals, dict) else {}


def _extract_last5(stats_row: Dict[str, Any]) -> Dict[str, Any]:
    if not stats_row:
        return {}
    fixtures = stats_row.get("fixtures") or {}
    last5 = fixtures.get("last_5") or fixtures.get("last5") or {}
    return last5 if isinstance(last5, dict) else {}


def _normalize_odds(odds_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalise odds into a flat dict for the main markets that builders use.
    Keys: HOME, AWAY, DRAW, O15, O25, O35, U35, BTTS_YES, BTTS_NO, HT_O05.
    """
    out: Dict[str, Any] = {
        "HOME": None,
        "AWAY": None,
        "DRAW": None,
        "O15": None,
        "O25": None,
        "O35": None,
        "U35": None,
        "BTTS_YES": None,
        "BTTS_NO": None,
        "HT_O05": None,
    }

    if not odds_list:
        return out

    for row in odds_list:
        bets = row.get("bets") or row.get("bookmakers") or []
        for b in bets:
            name = (b.get("name") or b.get("bet") or "").lower()
            values = b.get("values") or []

            # 1X2 / Winner
            if "1x2" in name or "winner" in name:
                for v in values:
                    label = (v.get("value") or v.get("label") or "").upper()
                    odd = v.get("odd")
                    if label in {"1", "HOME"}:
                        out["HOME"] = odd
                    elif label in {"2", "AWAY"}:
                        out["AWAY"] = odd
                    elif label in {"X", "DRAW"}:
                        out["DRAW"] = odd

            # Goals O/U (FT)
            if "over/under" in name or "goals" in name or "total goals" in name:
                for v in values:
                    val = (v.get("value") or "").lower()
                    hcap = str(v.get("handicap") or v.get("line") or "").replace(" ", "")
                    odd = v.get("odd")
                    if val == "over":
                        if hcap in {"1.5", "1,5"}:
                            out["O15"] = odd
                        elif hcap in {"2.5", "2,5"}:
                            out["O25"] = odd
                        elif hcap in {"3.5", "3,5"}:
                            out["O35"] = odd
                    elif val == "under":
                        if hcap in {"3.5", "3,5"}:
                            out["U35"] = odd

            # BTTS
            if "both teams to score" in name or "btts" in name:
                for v in values:
                    val = (v.get("value") or "").lower()
                    odd = v.get("odd")
                    if val == "yes":
                        out["BTTS_YES"] = odd
                    elif val == "no":
                        out["BTTS_NO"] = odd

            # First-half over 0.5 goals
            if "1st half" in name or "first half" in name:
                for v in values:
                    val = (v.get("value") or "").lower()
                    hcap = str(v.get("handicap") or "").replace(" ", "")
                    odd = v.get("odd")
                    if val == "over" and hcap in {"0.5", "0,5"}:
                        out["HT_O05"] = odd

    return out


def build_all_data(
    fixtures: List[Dict[str, Any]],
    odds: List[Dict[str, Any]],
    standings: List[Dict[str, Any]],
    team_stats: List[Dict[str, Any]],
    h2h: List[Dict[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """
    Primary public entrypoint for the aggregation layer.

    Returns:
        Dict[fixture_id] -> enriched data dict.
    """
    fx_index = _index_fixtures(fixtures)
    odds_index = _index_odds(odds)
    stats_index = _index_team_stats(team_stats)
    standings_index = _index_standings(standings)
    h2h_index = _index_h2h(h2h)

    all_data: Dict[int, Dict[str, Any]] = {}

    for fid, fx in fx_index.items():
        league = fx.get("league") or {}
        league_id = league.get("id")
        season = league.get("season")

        home_team = (fx.get("teams") or {}).get("home") or {}
        away_team = (fx.get("teams") or {}).get("away") or {}
        home_id = home_team.get("id")
        away_id = away_team.get("id")

        home_stats = stats_index.get((league_id, home_id), {})
        away_stats = stats_index.get((league_id, away_id), {})

        league_standings = standings_index.get(league_id, {})
        home_stand = league_standings.get(home_id)
        away_stand = league_standings.get(away_id)

        o = _normalize_odds(odds_index.get(fid, []))

        all_data[fid] = {
            "fixture": fx,
            "league_id": league_id,
            "season": season,
            "home_team": home_id,
            "away_team": away_id,
            "home_form": _extract_form(home_stats),
            "away_form": _extract_form(away_stats),
            "home_goals": _extract_goals_block(home_stats),
            "away_goals": _extract_goals_block(away_stats),
            "home_last5": _extract_last5(home_stats),
            "away_last5": _extract_last5(away_stats),
            "home_standings": home_stand,
            "away_standings": away_stand,
            "odds": o,
            "h2h_last": h2h_index.get(fid, []),
        }

    return all_data
