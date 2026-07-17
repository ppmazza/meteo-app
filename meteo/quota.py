"""Contatore locale del consumo API Open-Meteo.

Open-Meteo non espone header di rate limit: questo modulo tiene un registro
locale delle chiamate e ne stima il peso secondo le regole documentate.
È una stima, non un dato ufficiale: il limite è per IP e potrebbe essere
condiviso con altri client sulla stessa uscita di rete.
"""

import json
import time
from pathlib import Path

LEDGER = Path(".cache/usage.jsonl")
LEDGER.parent.mkdir(exist_ok=True)

LIMITS = {"minute": 600, "hour": 5_000, "day": 10_000}
WINDOWS = {"minute": 60, "hour": 3_600, "day": 86_400}


def estimate_weight(n_vars: int, n_days: int, n_locations: int = 1) -> float:
    """Peso stimato di una richiesta.

    Formula documentata da Open-Meteo:
        weight = nLocations * (nDays / 14) * (nVariables / 10)
    I fattori NON hanno floor individuali: una richiesta con poche variabili
    o pochi giorni può pesare meno di 1. Il floor si applica al totale,
    perché una richiesta normale conta comunque come una chiamata.
    """
    return max(1.0, n_locations * (n_days / 14) * (n_vars / 10))


def check_budget(weight: float, windows: tuple[str, ...] = ("hour", "day")) -> str | None:
    """Messaggio d'errore se la richiesta sforerebbe una delle finestre indicate.
    """
    u = usage()
    for name in windows:
        d = u[name]
        if d["used"] + weight > d["limit"]:
            return (
                f"Richiesta stimata in ~{weight:,.0f} chiamate: sforerebbe il limite "
                f"'{name}' ({d['used']:,.0f}/{d['limit']:,} già consumate). Riprova più tardi."
            )
    return None

def record(weight: float, endpoint: str) -> None:
    """Registra una chiamata andata a buon fine."""
    with LEDGER.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "weight": weight, "endpoint": endpoint}) + "\n")


def _entries() -> list[dict]:
    if not LEDGER.exists():
        return []
    with LEDGER.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def usage() -> dict:
    """Consumo stimato nelle tre finestre mobili."""
    now = time.time()
    entries = _entries()
    out = {}
    for name, span in WINDOWS.items():
        used = sum(e["weight"] for e in entries if now - e["ts"] < span)
        out[name] = {"used": used, "limit": LIMITS[name], "pct": 100 * used / LIMITS[name]}
    return out


def prune(max_age: int = 2 * 86_400) -> None:
    """Elimina le voci più vecchie di max_age secondi."""
    now = time.time()
    kept = [e for e in _entries() if now - e["ts"] < max_age]
    with LEDGER.open("w") as f:
        for e in kept:
            f.write(json.dumps(e) + "\n")