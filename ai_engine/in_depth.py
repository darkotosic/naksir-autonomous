# ai_engine/in_depth.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import os
from openai import OpenAI

# ----------------------------------------------------------------------
# OpenAI klijent (fail-safe: ako nema API key-a, analiza se preskače)
# ----------------------------------------------------------------------

API_KEY = os.getenv("OPENAI_API_KEY")

if API_KEY:
    client: Optional[OpenAI] = OpenAI(api_key=API_KEY)
else:
    client = None
    print("[IN_DEPTH] WARNING: OPENAI_API_KEY not set -> AI analysis will be skipped.")


# ----------------------------------------------------------------------
# Helperi za ekstrakciju iz all_data.json
# ----------------------------------------------------------------------

def _safe_response_block(all_data: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """
    Vrati listu dict-ova iz all_data[key]["response"], ili [] ako ne postoji.
    """
    block = all_data.get(key, {})
    resp = block.get("response", [])
    if isinstance(resp, list):
        return [x for x in resp if isinstance(x, dict)]
    return []


def _find_fixture_record(fixture_id: int, all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pronađi puni zapis fixture-a u all_data["fixtures"]["response"] po ID-u.
    """
    for row in _safe_response_block(all_data, "fixtures"):
        fx = row.get("fixture", {})
        if fx.get("id") == fixture_id:
            return row
    return {}


def _flatten_standings_for_league(league_id: int, all_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Vrati listu svih standings redova (timova) za dati league_id.
    Struktura API-FOOTBALL standings:
      standings.response[*].league.standings -> lista listi (grupe)
    """
    rows: List[Dict[str, Any]] = []
    for r in _safe_response_block(all_data, "standings"):
        league = r.get("league", {})
        if league.get("id") != league_id:
            continue
        standings = league.get("standings", [])
        # standings je lista listi – flatten
        for group in standings:
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, dict):
                        rows.append(item)
    return rows


def _find_team_stats(league_id: int, team_id: int, all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pronađi team statistics zapis za kombinaciju (league_id, team_id).
    """
    for row in _safe_response_block(all_data, "team_stats"):
        team = row.get("team", {})
        league = row.get("league", {})
        if team.get("id") == team_id and league.get("id") == league_id:
            return row
    return {}


def _collect_h2h_for_pair(home_id: int, away_id: int, all_data: Dict[str, Any], max_matches: int = 5) -> List[Dict[str, Any]]:
    """
    Skupi poslednjih max_matches H2H mečeva za dati par timova (u oba smera).
    """
    matches: List[Dict[str, Any]] = []
    for row in _safe_response_block(all_data, "h2h"):
        teams = row.get("teams", {})
        h = teams.get("home", {})
        a = teams.get("away", {})
        h_id = h.get("id")
        a_id = a.get("id")
        if {h_id, a_id} == {home_id, away_id}:
            matches.append(row)

    # sortiraj po datumu ako postoji fixture.date
    def _ts(x: Dict[str, Any]) -> int:
        fx = x.get("fixture", {})
        return int(fx.get("timestamp") or 0)

    matches.sort(key=_ts, reverse=True)
    return matches[:max_matches]


def _find_prediction_for_fixture(fixture_id: int, all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pronađi predictions zapis za dati fixture_id.
    """
    for row in _safe_response_block(all_data, "predictions"):
        fx = row.get("fixture", {})
        if fx.get("id") == fixture_id:
            return row
    return {}


def _collect_injuries_for_teams(league_id: int, team_ids: List[int], all_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Vrati sve injury zapise za zadate timove u okviru lige.
    """
    out: List[Dict[str, Any]] = []
    for row in _safe_response_block(all_data, "injuries"):
        league = row.get("league", {})
        team = row.get("team", {})
        if league.get("id") == league_id and team.get("id") in team_ids:
            out.append(row)
    return out


def _summarize_h2h(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Kompaktni summary H2H serije (za prompt).
    """
    total = len(matches)
    if total == 0:
        return {"total": 0}

    goals_home = 0
    goals_away = 0
    over15 = 0
    over25 = 0
    btts = 0

    short_list: List[Dict[str, Any]] = []

    for row in matches:
        fixture = row.get("fixture", {})
        goals = row.get("goals", {})
        gh = goals.get("home") or 0
        ga = goals.get("away") or 0
        goals_home += gh
        goals_away += ga

        total_goals = (gh or 0) + (ga or 0)
        if total_goals >= 2:
            over15 += 1
        if total_goals >= 3:
            over25 += 1
        if gh > 0 and ga > 0:
            btts += 1

        short_list.append(
            {
                "date": fixture.get("date"),
                "goals_home": gh,
                "goals_away": ga,
            }
        )

    return {
        "total_matches": total,
        "avg_goals_home": goals_home / total,
        "avg_goals_away": goals_away / total,
        "over_1_5_count": over15,
        "over_2_5_count": over25,
        "btts_count": btts,
        "last_matches": short_list,
    }


def _summarize_team_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Iz team_stats odgovora izvuci samo ono što je korisno za prompt
    (da ne šaljemo ceo ogroman JSON).
    """
    if not stats:
        return {}

    goals = stats.get("goals", {})
    fixtures = stats.get("fixtures", {})
    form = stats.get("form")  # npr. "WDWLW"
    attacks = stats.get("attacks", {})
    lineups = stats.get("lineups", [])

    return {
        "form": form,
        "played": fixtures.get("played"),
        "wins": fixtures.get("wins"),
        "draws": fixtures.get("draws"),
        "loses": fixtures.get("loses"),
        "goals_for": goals.get("for"),
        "goals_against": goals.get("against"),
        "attacks": attacks,
        "preferred_lineups": [
            {"formation": l.get("formation"), "played": l.get("played")}
            for l in lineups[:3] if isinstance(l, dict)
        ],
    }


def _summarize_standings_for_teams(standings: List[Dict[str, Any]], team_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Iz standings list-e izvuci samo redove za zadate timove.
    """
    out: List[Dict[str, Any]] = []
    for row in standings:
        team = row.get("team", {})
        if team.get("id") in team_ids:
            out.append(
                {
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "rank": row.get("rank"),
                    "points": row.get("points"),
                    "goals_diff": row.get("goalDiff"),
                    "form": row.get("form"),
                    "played": row.get("all", {}).get("played"),
                }
            )
    return out


def _summarize_prediction(pred: Dict[str, Any]) -> Dict[str, Any]:
    """
    Iz predictions odgovora izvuci kratak summary (home/away win %, draw %, goals tip).
    """
    if not pred:
        return {}

    win_or_draw = pred.get("win_or_draw")
    goals = pred.get("goals", {})
    advice = pred.get("advice")  # npr. "Home Win"

    percent = pred.get("percent", {})
    return {
        "advice": advice,
        "win_or_draw": win_or_draw,
        "percent_home": percent.get("home"),
        "percent_draw": percent.get("draw"),
        "percent_away": percent.get("away"),
        "goals_pred": goals,
    }


def _summarize_injuries(injuries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Kompaktni prikaz povreda / izostanaka za prompt.
    """
    out: List[Dict[str, Any]] = []
    for row in injuries:
        team = row.get("team", {})
        team_name = team.get("name")
        for player in row.get("players", []):
            if not isinstance(player, dict):
                continue
            out.append(
                {
                    "team": team_name,
                    "player_name": player.get("name"),
                    "reason": player.get("reason"),
                    "type": player.get("type"),
                    "status": player.get("status"),
                }
            )
    return out


# ----------------------------------------------------------------------
# Glavni context builder za jedan leg
# ----------------------------------------------------------------------

def _extract_basic_context_for_leg(leg: Dict[str, Any], all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Iz all_data.json pokupi najbitnije brojke za ovaj fixture:
    - fixture meta (liga, datum, status)
    - standings za oba tima
    - team statistics (form, goals for/against, linije)
    - h2h poslednjih 5 mečeva
    - predictions (ako postoje)
    - injuries (ako postoje)
    """
    fixture_id = leg["fixture_id"]

    # pun zapis o fixture-u
    fx_row = _find_fixture_record(fixture_id, all_data)
    fixture = fx_row.get("fixture", {})
    league = fx_row.get("league", {})
    teams = fx_row.get("teams", {})
    goals = fx_row.get("goals", {})

    league_id = int(league.get("id") or 0)
    home_team_id = int(teams.get("home", {}).get("id") or 0)
    away_team_id = int(teams.get("away", {}).get("id") or 0)
    team_ids = [tid for tid in (home_team_id, away_team_id) if tid]

    # standings
    standings_all = _flatten_standings_for_league(league_id, all_data)
    standings_slice = _summarize_standings_for_teams(standings_all, team_ids)

    # team stats
    home_stats_raw = _find_team_stats(league_id, home_team_id, all_data) if home_team_id else {}
    away_stats_raw = _find_team_stats(league_id, away_team_id, all_data) if away_team_id else {}
    home_stats = _summarize_team_stats(home_stats_raw)
    away_stats = _summarize_team_stats(away_stats_raw)

    # h2h
    h2h_matches = _collect_h2h_for_pair(home_team_id, away_team_id, all_data, max_matches=5) if team_ids else []
    h2h_summary = _summarize_h2h(h2h_matches)

    # predictions
    prediction_raw = _find_prediction_for_fixture(fixture_id, all_data)
    prediction_summary = _summarize_prediction(prediction_raw)

    # injuries
    injuries_raw = _collect_injuries_for_teams(league_id, team_ids, all_data)
    injuries_summary = _summarize_injuries(injuries_raw)

    ctx = {
        # osnovne stvari iz lega
        "home": leg["home"],
        "away": leg["away"],
        "league_name": leg.get("league_name"),
        "league_country": leg.get("league_country"),
        "market": leg.get("market"),
        "pick": leg.get("pick"),
        "odds": leg.get("odds"),
        "kickoff": leg.get("kickoff"),

        # fixture meta
        "fixture": {
            "id": fixture.get("id"),
            "date": fixture.get("date"),
            "status": fixture.get("status"),
            "venue": fixture.get("venue"),
        },

        # league meta
        "league": {
            "id": league_id,
            "name": league.get("name"),
            "country": league.get("country"),
            "season": league.get("season"),
            "round": league.get("round"),
        },

        # timovi + golovi
        "teams": teams,
        "goals": goals,

        # standings / forma / stats
        "standings_for_teams": standings_slice,
        "home_stats": home_stats,
        "away_stats": away_stats,

        # head-to-head summary
        "h2h": h2h_summary,

        # model predictions
        "prediction": prediction_summary,

        # povrede / izostanci
        "injuries": injuries_summary,
    }

    return ctx


def _build_prompt(leg: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """
    Prompt for GPT: produce 5–7 short, data-driven English sentences about the bet.
    Must be Play-Store compliant (no promises, no gambling guarantees).
    """
    return f"""
You are a professional football data analyst.

Using ONLY the structured information below, write 5 to 7 short, objective, football-focused sentences 
(no bullets, plain text, max ~900 characters) explaining the statistical context behind this betting pick. 
Keep it analytical, neutral, and focused on data trends such as form, goals, H2H patterns, standings, 
and team strengths/weaknesses.

Language: English.
Tone: professional, concise, analytical.
Do NOT provide guarantees. Do NOT use persuasive gambling language. 
Do NOT mention that you are an AI. 
Avoid phrases like “this will win”, “high chance”, “guaranteed”, etc.
Stick strictly to describing statistical trends and contextual factors.

Basic info:
- League: {ctx["league"].get("country")} — {ctx["league"].get("name")} (season {ctx["league"].get("season")}, round {ctx["league"].get("round")})
- Match: {ctx.get("home")} vs {ctx.get("away")}
- Pick: {ctx.get("pick")} (market code: {ctx.get("market")}) @ odds {ctx.get("odds")}
- Kickoff (UTC): {ctx.get("kickoff")}

Structured context (summarised JSON):
- Fixture meta: {ctx.get("fixture")}
- Standings for these teams: {ctx.get("standings_for_teams")}
- Home team stats: {ctx.get("home_stats")}
- Away team stats: {ctx.get("away_stats")}
- H2H summary: {ctx.get("h2h")}
- Prediction model summary: {ctx.get("prediction")}
- Injuries / missing players: {ctx.get("injuries")}
""".strip()


# ----------------------------------------------------------------------
# Glavna funkcija za generisanje analize
# ----------------------------------------------------------------------

def _generate_analysis_text(leg: Dict[str, Any], all_data: Dict[str, Any]) -> List[str]:
    """
    Vraća listu 5–7 rečenica za jedan leg.
    Ako nema OPENAI_API_KEY ili nešto pukne, vraća prazan list –
    frontend onda samo neće prikazati in-depth layer.
    """
    if client is None:
        # nema API key-a -> tiho preskačemo
        return []

    try:
        ctx = _extract_basic_context_for_leg(leg, all_data)
        prompt = _build_prompt(leg, ctx)

        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            max_output_tokens=320,
        )

        # Defanzivno izvlačenje teksta iz Responses API outputa
        text = ""
        try:
            # novi Responses API: resp.output[0].content[0].text
            first_output = resp.output[0]
            first_content = first_output.content[0]
            text = getattr(first_content, "text", str(resp))
        except Exception:
            text = str(resp)

        # Rascepi na rečenice; uzmi 5–7
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        return [s + "." for s in sentences[:7]]
    except Exception as e:
        print(f"[IN_DEPTH] Error for fixture {leg.get('fixture_id')}: {e}")
        return []


# ----------------------------------------------------------------------
# Public entrypoint za morning_run
# ----------------------------------------------------------------------

def attach_in_depth_analysis(ticket_sets: Dict[str, Any], all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prolazi kroz sve setove/tikete/legove i dodaje 'analysis': [ ... ] na svaki leg.

    Ulaz/izlaz: isti dict kao u tickets.json, samo obogaćen.
    Ako nema OPENAI_API_KEY ili nešto pukne, existing struktura ostaje nepromenjena.
    """
    if client is None:
        # nema smisla raditi iteraciju ako nema AI – samo vrati original
        return ticket_sets

    sets = ticket_sets.get("sets", [])
    if not isinstance(sets, list):
        return ticket_sets

    for set_obj in sets:
        tickets = set_obj.get("tickets", [])
        if not isinstance(tickets, list):
            continue

        for ticket in tickets:
            legs = ticket.get("legs", [])
            if not isinstance(legs, list):
                continue

            for leg in legs:
                if not isinstance(leg, dict):
                    continue
                # preskoči ako već postoji analiza (da ne trošimo duplo)
                if leg.get("analysis"):
                    continue

                leg["analysis"] = _generate_analysis_text(leg, all_data)

    return ticket_sets
