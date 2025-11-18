import json
import os
from pathlib import Path
from datetime import date
from typing import Any, Optional, Union

# Root cache folder: /cache
CACHE_ROOT = Path(__file__).resolve().parent.parent / "cache"


# -----------------------------
# Internal Utilities
# -----------------------------

def _ensure_dir(path: Union[str, Path]) -> None:
    """Create directory if not exists."""
    Path(path).mkdir(parents=True, exist_ok=True)


def _date_str(d: Optional[date] = None) -> str:
    return (d or date.today()).isoformat()


def _full_path(rel_path: str, day: Optional[date] = None) -> Path:
    """Build absolute path: /cache/YYYY-MM-DD/<rel_path>."""
    ds = _date_str(day)
    base = CACHE_ROOT / ds
    _ensure_dir(base)
    fp = base / rel_path
    _ensure_dir(fp.parent)
    return fp


# -----------------------------
# Public API
# -----------------------------

def write_json(name: str, data: Any, day: Optional[date] = None) -> Path:
    """
    Write JSON to /cache/YYYY-MM-DD/name.
    Returns filepath.
    """
    fp = _full_path(name, day)
    with fp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return fp


def read_json(name: str, day: Optional[date] = None) -> Optional[Any]:
    """
    Read JSON from /cache/YYYY-MM-DD/name.
    Returns None if missing.
    """
    fp = _full_path(name, day)
    if not fp.exists():
        return None
    try:
        with fp.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def exists(name: str, day: Optional[date] = None) -> bool:
    """Check if file exists in daily cache."""
    fp = _full_path(name, day)
    return fp.exists()


def list_day(day: Optional[date] = None) -> list[str]:
    """
    List all files inside /cache/YYYY-MM-DD.
    """
    ds = _date_str(day)
    day_dir = CACHE_ROOT / ds
    if not day_dir.exists():
        return []
    return [str(p.relative_to(day_dir)) for p in day_dir.rglob("*") if p.is_file()]


def ensure_subdir(name: str, day: Optional[date] = None) -> Path:
    """
    Create subdirectory inside daily cache manually.
    Useful for: standings/, stats/, h2h/
    """
    fp = _full_path(name, day)
    _ensure_dir(fp)
    return fp


# -----------------------------
# Advanced — fallback loader
# -----------------------------

def read_or_fallback(
    name: str,
    primary_day: Optional[date] = None,
    fallback_days: int = 2
) -> Optional[Any]:
    """
    Try reading today's cache first; if missing, fallback to N previous days.
    Used in Fallback AI Guardrails (self-healing).
    """
    # 1. Today
    today_value = read_json(name, day=primary_day)
    if today_value is not None:
        return today_value

    # 2. Fallback loop
    start = primary_day or date.today()
    for i in range(1, fallback_days + 1):
        prev = start.fromordinal(start.toordinal() - i)
        val = read_json(name, day=prev)
        if val is not None:
            return val

    return None


# -----------------------------
# Diagnostic utils (for Logs)
# -----------------------------

def cache_status(day: Optional[date] = None) -> dict:
    """
    Returns summary:
      - files count
      - structure layout
      - missing common components
    """
    ds = _date_str(day)
    day_dir = CACHE_ROOT / ds
    missing = []
    files = list_day(day)

    # Standard expected files
    expected = [
        "fixtures.json",
        "odds.json",
        "standings",
        "stats",
        "h2h",
    ]

    for e in expected:
        p = day_dir / e
        if not p.exists():
            missing.append(e)

    return {
        "date": ds,
        "files_total": len(files),
        "missing": missing,
        "files": files,
    }
