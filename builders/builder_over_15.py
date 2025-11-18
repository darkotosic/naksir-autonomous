# builders/builder_over_15.py
from typing import List, Dict, Any
from builders.mixer import mix_tickets

# očekujemo da ingest već ima fixtures + odds u cache ili ih primiš kroz parametar

def build_over_15_legs(fixtures: Dict[str, Any], odds: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Iz fixtures + odds pravi legs za tržište Over 1.5.

    Return: list[leg]
    leg struktura (predlog standarda):
      {
        "fixture_id": 12345,
        "league_name": "England – Premier League",
        "home": "Arsenal",
        "away": "Burnley",
        "market": "O15",
        "pick": "Over 1.5 Goals",
        "odds": 1.23,
        "kickoff": "2025-11-17T20:00:00Z"
      }
    """
    legs = []

    # OVDE ubacuješ postojeće filtere iz focus-bets / Telegram-Tickets:
    # - allow_ligs
    # - max/min odds
    # - forma, golovi, xG...
    for f in fixtures.get("response", []):
        fixture_id = f.get("fixture", {}).get("id")
        # ... izvučeš ligu, timove, vreme, itd.
        # ... nađeš odgovarajući odds u "odds" strukturi
        # ... primeniš pravila (1.10–1.40, bar 60% scoring metrics, itd.)
        # ako meč zadovoljava:
        leg = {
            "fixture_id": fixture_id,
            "league_name": f.get("league", {}).get("name"),
            "home": f.get("teams", {}).get("home", {}).get("name"),
            "away": f.get("teams", {}).get("away", {}).get("name"),
            "market": "O15",
            "pick": "Over 1.5 Goals",
            "odds": 1.23,  # TODO: izračunaj iz odds data
            "kickoff": f.get("fixture", {}).get("date"),
        }
        legs.append(leg)

    return legs
