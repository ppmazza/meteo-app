"""Client per le API Open-Meteo (geocoding + archivio storico ERA5)."""

import hashlib
from pathlib import Path

import pandas as pd
import requests
import time
from meteo.quota import check_budget, estimate_weight, record

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "precipitation_hours",
]

# ERA5 pubblica con ~5 giorni di ritardo: teniamo un margine di sicurezza.
ERA5_LAG_DAYS = 6
RETRY_WAIT_S = 65
MAX_RETRIES = 2

def geocode(name: str, count: int = 5) -> list[dict]:
    """Cerca una località, restituisce una lista di candidati."""
    r = requests.get(
        GEOCODING_URL,
        params={"name": name, "count": count, "language": "it"},
        timeout=15,
    )
    if r.status_code == 429:
        raise RuntimeError("Limite di richieste Open-Meteo raggiunto (geocoding).")
    r.raise_for_status()
    record(1.0, "geocoding")
    return r.json().get("results", [])


def _cache_path(lat: float, lon: float, start: str, end: str) -> Path:
    # L'hash delle variabili nella chiave: cambiare DAILY_VARS invalida la cache.
    vars_hash = hashlib.md5(",".join(DAILY_VARS).encode()).hexdigest()[:6]
    return CACHE_DIR / f"{lat:.4f}_{lon:.4f}_{start}_{end}_{vars_hash}.parquet"


def fetch_daily_history(
    lat: float,
    lon: float,
    start: str = "2010-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Scarica lo storico daily per una località, con cache su disco.
    """
    if end is None:
        end = (pd.Timestamp.today() - pd.Timedelta(days=ERA5_LAG_DAYS)).strftime("%Y-%m-%d")

    path = _cache_path(lat, lon, start, end)
    if path.exists():
        return pd.read_parquet(path)

    n_days = (pd.Timestamp(end) - pd.Timestamp(start)).days + 1
    weight = estimate_weight(len(DAILY_VARS), n_days)

    if (msg := check_budget(weight)) is not None:
        raise RuntimeError(msg)

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_VARS),
        "timezone": "auto",
    }

    for attempt in range(MAX_RETRIES + 1):
        r = requests.get(ARCHIVE_URL, params=params, timeout=180)
        if r.status_code != 429:
            break
        if attempt == MAX_RETRIES:
            raise RuntimeError(
                "Limite di richieste Open-Meteo raggiunto e retry esauriti. "
                "Riprova tra qualche minuto."
            )
        time.sleep(RETRY_WAIT_S)

    r.raise_for_status()
    record(weight, "archive")

    df = pd.DataFrame(r.json()["daily"])
    df["time"] = pd.to_datetime(df["time"])
    df.to_parquet(path)
    return df