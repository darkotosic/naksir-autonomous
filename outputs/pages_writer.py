from pathlib import Path
import json
from datetime import date

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"

def write_tickets_json(ticket_sets: dict) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "date": date.today().isoformat(),
        "sets": ticket_sets["sets"],
    }
    fp = PUBLIC_DIR / "tickets.json"
    with fp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
