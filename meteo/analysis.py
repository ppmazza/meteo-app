import pandas as pd


def day_across_years(df: pd.DataFrame, month: int, day: int,
                     window: int = 0) -> pd.DataFrame:
    """Per ogni anno, media delle variabili nella finestra ±window giorni
    attorno al giorno (month, day)."""
    # 2001: non bisestile
    doy_target = pd.Timestamp(year=2001, month=month, day=day).dayofyear
    doy = df["time"].dt.dayofyear
    # distanza circolare sul day-of-year (gestisce il wrap di fine anno)
    dist = (doy - doy_target).abs()
    dist = pd.concat([dist, 365 - dist], axis=1).min(axis=1)
    mask = dist <= window
    out = (df[mask]
           .assign(year=df["time"].dt.year)
           .groupby("year")
           .mean(numeric_only=True)
           .reset_index())
    return out
