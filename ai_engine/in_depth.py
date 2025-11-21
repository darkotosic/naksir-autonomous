# ai_engine/in_depth.py
from __future__ import annotations

from typing import Any, Dict, List

import os
from openai import OpenAI

API_KEY = os.getenv("OPENAI_API_KEY")

if API_KEY:
    client = OpenAI(api_key=API_KEY)
else:
    client = None
    print("[IN_DEPTH] WARNING: OPENAI_API_KEY not set -> AI analysis will be skipped.")


def _extract_basic_context_for_leg(leg: Dict[str, Any], all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Iz all_data.json pokupi najbitnije brojke za ovaj fixture:
    - recent form obe ekipe
    - prosečan broj golova postignut/primljen
    - h2h ako postoji
    - standings pozicije

    Ovaj deo MORAŠ da prilagodiš konkretnoj strukturi all_data.json.
    Ovde je samo šablon.
    """
    fixture_id = leg["fixture_id"]

    # PSEUDOKOD – prilagodi prema tome kako čuvaš response u all_data.json
    fixtures = {
        f["fixture"]["id"]: f
        for f in all_data.get("fixtures", {}).get("response", [])
        if isinstance(f, dict) and f.get("fixture", {}).get("id") is not None
    }

    fixture = fixtures.get(fixture_id, {})

    # primer neke meta info; prilagodi ključ
    league = fixture.get("league", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})

    ctx = {
        "home": leg["home"],
        "away": leg["away"],
        "league_name": leg.get("league_name"),
        "league_country": leg.get("league_country"),
        "market": leg.get("market"),
        "pick": leg.get("pick"),
        "odds": leg.get("odds"),
        "kickoff": leg.get("kickoff"),
        "fixture_raw": {
            "league": league,
            "teams": teams,
            "goals": goals,
        },
        # TODO: ubaci standings, form, xG, h2h iz all_data
    }
    return ctx


def _build_prompt(leg: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    """
    Prompt koji od GPT-a traži 5–7 rečenica analize za jedan meč.
    Drži ga kratak da ne gori previše tokena.
    """
    return f"""
You are a professional football betting analyst.

Write 5 to 7 short, data-driven sentences (no bullets, plain text, max ~900 characters total) explaining why the betting pick might be reasonable or risky.

Language: Serbian (Latin, casual but professional).
Do NOT mention that you are an AI. Do NOT mention that this is not guaranteed. Focus on stats and context.

Basic info:
- League: {ctx.get("league_country")} — {ctx.get("league_name")}
- Match: {ctx.get("home")} vs {ctx.get("away")}
- Pick: {ctx.get("pick")} (market code: {ctx.get("market")}) @ odds {ctx.get("odds")}
- Kickoff (UTC): {ctx.get("kickoff")}

Available raw data snapshot (may be incomplete, use only if useful):
{ctx.get("fixture_raw")}
""".strip()


def _generate_analysis_text(leg: Dict[str, Any], all_data: Dict[str, Any]) -> List[str]:
    """
    Vraća listu 5–7 rečenica za jedan leg.
    Ako nema OPENAI_API_KEY ili nešto pukne, vraća prazan list –
    frontend onda samo neće prikazati in-depth layer.
    """
    # ako nema klijenta (nema API key-a) -> skip
    if client is None:
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

        # Izvuci čist tekst – shape se može menjati, zato je ovo malo defenzivno
        text = ""
        try:
            text = resp.output[0].content[0].text  # možeš kasnije da prilagodiš po potrebi
        except Exception:
            text = str(resp)

        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
        return [s + "." for s in sentences[:7]]
    except Exception as e:
        print(f"[IN_DEPTH] Error for fixture {leg.get('fixture_id')}: {e}")
        return []


def attach_in_depth_analysis(ticket_sets: Dict[str, Any], all_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prolazi kroz sve setove/tikete/legove i dodaje 'analysis': [ ... ] na svaki leg.

    Ulaz/izlaz: isti dict kao u tickets.json, samo obogaćen.
    """
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
