"""Aggregazioni sulle serie storiche daily."""

import pandas as pd
import numpy as np

# Come aggregare ogni variabile sulla finestra ±window giorni.
# Temperature e venti: media (o max per le raffiche). Accumuli: somma.
AGG = {
    "temperature_2m_max": "mean",
    "temperature_2m_min": "mean",
    "temperature_2m_mean": "mean",
    "precipitation_sum": "sum",
    "rain_sum": "sum",
    "snowfall_sum": "sum",
    "precipitation_hours": "sum",
    "wind_speed_10m_max": "mean",
    "wind_gusts_10m_max": "max",
    "sunshine_duration": "mean",
}


def day_across_years(
    df: pd.DataFrame,
    month: int,
    day: int,
    window: int = 0,
    complete_only: bool = True,
) -> pd.DataFrame:
    """Per ogni anno, aggrega le variabili nella finestra ±window giorni
    attorno al giorno (month, day).

    La distanza è calcolata in modo circolare sul day-of-year, quindi la
    finestra attraversa correttamente il capodanno. Attenzione però: il
    raggruppamento è per anno solare, quindi per date a cavallo di gennaio
    i giorni di fine dicembre finiscono nell'anno *successivo* rispetto
    all'inverno cui appartengono meteorologicamente.

    Con complete_only=True vengono scartati gli anni con finestra incompleta
    (tipicamente il primo e l'ultimo della serie): sulle variabili sommate
    una finestra tronca produce un valore artificialmente basso, che
    distorcerebbe la regressione.
    """
    doy_target = pd.Timestamp(year=2001, month=month, day=day).dayofyear  # 2001 non bisestile
    doy = df["time"].dt.dayofyear
    dist = (doy - doy_target).abs()
    dist = pd.concat([dist, 365 - dist], axis=1).min(axis=1)

    sub = df.loc[dist <= window].copy()
    sub["year"] = sub["time"].dt.year

    agg = {c: how for c, how in AGG.items() if c in sub.columns}
    out = sub.groupby("year").agg(agg)
    out["n_days"] = sub.groupby("year").size()
    out = out.reset_index()

    if complete_only:
        out = out[out["n_days"] == 2 * window + 1].reset_index(drop=True)

    return out

def smooth(series: pd.Series, window: int = 11) -> pd.Series:
    """Media mobile centrata. La finestra di 11 anni è convenzionale in
    climatologia: abbastanza lunga da sopprimere la variabilità interannuale,
    abbastanza corta da non appiattire i trend decennali."""
    return series.rolling(window, center=True, min_periods=window // 2 + 1).mean()


def add_derived(trend: pd.DataFrame) -> pd.DataFrame:
    """Colonne derivate utili per i grafici."""
    out = trend.copy()

    # Escursione termica giornaliera (diurnal temperature range).
    out["dtr"] = out["temperature_2m_max"] - out["temperature_2m_min"]

    # snowfall_sum è in cm di neve: ~7 cm ≈ 10 mm di acqua equivalente.
    out["snow_mm"] = out["snowfall_sum"] * 10 / 7
    out["snow_share"] = 100 * out["snow_mm"] / out["precipitation_sum"].replace(0, np.nan)
    out["intensity"] = out["precipitation_sum"] / out["precipitation_hours"].replace(0, np.nan)

    return out