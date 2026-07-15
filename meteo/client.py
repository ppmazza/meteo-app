import pandas as pd
import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

def geocode(name: str, count: int = 5) -> list[dict]:
    """Cerca una località, restituisce lista di candidati."""
    params = {"name": name, "count": count, "language": "it"}
    r = requests.get(GEOCODING_URL, params=params)
    r.raise_for_status()
    return r.json().get("results", [])

def fetch_daily_history(lat: float, lon: float,
                        start: str = "1940-01-01",
                        end: str | None = None) -> pd.DataFrame:
    """Scarica lo storico daily completo per una località."""
    if end is None:
        end = (pd.Timestamp.today() - pd.Timedelta(days=6)).strftime("%Y-%m-%d")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                 "precipitation_sum,wind_speed_10m_max",
        "timezone": "auto",
    }
    r = requests.get(ARCHIVE_URL, params=params)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["daily"])
    df["time"] = pd.to_datetime(df["time"])
    return df
