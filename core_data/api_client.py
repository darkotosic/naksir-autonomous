import os
import time
import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Konfiguracija
# ---------------------------------------------------------------------

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_BASE = "https://v3.football.api-sports.io"
TIMEZONE = os.getenv("API_FOOTBALL_TIMEZONE", "Europe/Belgrade")

# Minimalna pauza između poziva da ne čekićamo API (u sekundama)
MIN_REQUEST_INTERVAL = float(os.getenv("API_FOOTBALL_MIN_INTERVAL", "0.3"))

# Retry konfiguracija
MAX_RETRIES = int(os.getenv("API_FOOTBALL_MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = float(os.getenv("API_FOOTBALL_BACKOFF_BASE", "0.8"))

# Interno stanje za jednostavan QPS limiter
_last_request_ts: float = 0.0


# ---------------------------------------------------------------------
# Interni helperi
# ---------------------------------------------------------------------

def _ensure_api_key() -> None:
    if not API_KEY:
        raise RuntimeError("API_FOOTBALL_KEY environment variable not set")


def _respect_qps_limit() -> None:
    """
    Vrlo jednostavan limiter:
    - obezbedi da je bar MIN_REQUEST_INTERVAL prošlo između 2 poziva.
    """
    global _last_request_ts
    now = time.time()
    delta = now - _last_request_ts
    if delta < MIN_REQUEST_INTERVAL:
        sleep_for = MIN_REQUEST_INTERVAL - delta
        time.sleep(sleep_for)
    _last_request_ts = time.time()


def _request(
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    method: str = "GET",
    timeout: int = 20,
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """
    Centralni HTTP wrapper za sve pozive API-FOOTBALL-a.
    """
    _ensure_api_key()
    if params is None:
        params = {}

    url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
    headers = {
        "x-apisports-key": API_KEY,
        "Accept": "application/json",
    }

    attempt = 0
    last_exc: Optional[Exception] = None
    while attempt < max_retries:
        attempt += 1
        try:
            _respect_qps_limit()
            resp = requests.request(method, url, headers=headers, params=params, timeout=timeout)

            logger.debug(
                "API-Football request: %s %s params=%s status=%s",
                method,
                url,
                params,
                resp.status_code,
            )

            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "API-Football transient error (status=%s), attempt=%s/%s",
                    resp.status_code,
                    attempt,
                    max_retries,
                )
                try:
                    data = resp.json()
                except Exception:
                    data = {"raw": resp.text[:300]}
                last_exc = RuntimeError(f"Transient API error: {resp.status_code}, body={data}")
            elif resp.status_code != 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {"raw": resp.text[:300]}
                raise RuntimeError(
                    f"API error: status={resp.status_code}, url={url}, params={params}, body={data}"
                )
            else:
                try:
                    return resp.json()
                except ValueError as e:
                    logger.warning("JSON decode error on attempt %s: %s", attempt, e)
                    last_exc = e

        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(
                "API-Football network/timeout error on attempt %s/%s: %s",
                attempt,
                max_retries,
                e,
            )
            last_exc = e

        if attempt < max_retries:
            backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            time.sleep(backoff)

    raise RuntimeError(f"API-Football request failed after {max_retries} attempts: {last_exc}")


# ---------------------------------------------------------------------
# Status / health
# ---------------------------------------------------------------------

def get_api_status() -> Dict[str, Any]:
    """
    Wrapper za /status
    """
    path = "status"
    resp = _request(path, params={})

    status_url = f"{API_BASE.rstrip('/')}/{path}"
    headers = {
        "x-apisports-key": API_KEY,
        "Accept": "application/json",
    }
    rl_info: Dict[str, Any] = {}
    try:
        raw_resp = requests.get(status_url, headers=headers, timeout=10)
        rl_info = {
            "x-ratelimit-requests-limit": raw_resp.headers.get("x-ratelimit-requests-limit"),
            "x-ratelimit-requests-remaining": raw_resp.headers.get("x-ratelimit-requests-remaining"),
            "x-ratelimit-requests-reset": raw_resp.headers.get("x-ratelimit-requests-reset"),
        }
    except Exception as e:
        logger.warning("Failed to fetch rate-limit headers: %s", e)

    errors = resp.get("errors")
    ok = not errors and (resp.get("response") is not None)

    return {
        "ok": ok,
        "raw": resp,
        "rate_limit": rl_info,
    }


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

def fetch_fixtures_by_date(target_date: str) -> Dict[str, Any]:
    """
    /fixtures?date=YYYY-MM-DD&timezone=TZ
    """
    params = {
        "date": target_date,
        "timezone": TIMEZONE,
    }
    resp = _request("fixtures", params=params)
    try:
        results = resp.get("results")
        resp_len = len(resp.get("response") or [])
        errors = resp.get("errors")
        logger.info(
            "[API-DEBUG] fixtures date=%s results=%s response_len=%s errors=%s",
            target_date,
            results,
            resp_len,
            errors,
        )
    except Exception:
        logger.warning("[API-DEBUG] fixtures raw for %s: %r", target_date, resp)
    return resp


# ---------------------------------------------------------------------
# Odds
# ---------------------------------------------------------------------

def fetch_odds_by_date(target_date: str) -> Dict[str, Any]:
    """
    /odds?date=YYYY-MM-DD&timezone=TZ
    """
    params = {
        "date": target_date,
        "timezone": TIMEZONE,
    }
    resp = _request("odds", params=params)
    try:
        results = resp.get("results")
        resp_len = len(resp.get("response") or [])
        errors = resp.get("errors")
        logger.info(
            "[API-DEBUG] odds date=%s results=%s response_len=%s errors=%s",
            target_date,
            results,
            resp_len,
            errors,
        )
    except Exception:
        logger.warning("[API-DEBUG] odds raw for %s: %r", target_date, resp)
    return resp


# ---------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------

def fetch_standings(league_id: int, season: int) -> Dict[str, Any]:
    """
    /standings?league={league_id}&season={season}
    """
    return _request("standings", params={"league": league_id, "season": season})


# ---------------------------------------------------------------------
# Team Statistics
# ---------------------------------------------------------------------

def fetch_team_stats(league_id: int, season: int, team_id: int) -> Dict[str, Any]:
    """
    /teams/statistics?league={league_id}&season={season}&team={team_id}
    """
    return _request(
        "teams/statistics",
        params={
            "league": league_id,
            "season": season,
            "team": team_id,
        },
    )


# ---------------------------------------------------------------------
# H2H (Head-to-Head)
# ---------------------------------------------------------------------

def fetch_h2h(home_id: int, away_id: int, last: int = 5) -> Dict[str, Any]:
    """
    /fixtures/headtohead?h2h={home_id}-{away_id}&last={last}
    """
    h2h_str = f"{home_id}-{away_id}"
    return _request(
        "fixtures/headtohead",
        params={
            "h2h": h2h_str,
            "last": last,
        },
                )
