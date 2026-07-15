import plotly.express as px
import streamlit as st

from meteo.analysis import add_derived, day_across_years
from meteo.client import fetch_daily_history, geocode
from meteo.quota import usage

st.set_page_config(page_title="Dati meteo storici", layout="wide")
st.title("🌤️ Analisi serie storiche meteo per località")


# --------------------------------------------------------------------------
# Funzioni cachate
# --------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def cached_geocode(name: str):
    return geocode(name)


@st.cache_data(show_spinner="Scarico lo storico...")
def load_history(lat: float, lon: float):
    return fetch_daily_history(lat, lon)


# --------------------------------------------------------------------------
# Sidebar: consumo API
# --------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Consumo API (stima)")
    u = usage()
    for key, label in [("minute", "Ultimo minuto"), ("hour", "Ultima ora"), ("day", "Oggi")]:
        d = u[key]
        st.progress(
            min(d["pct"] / 100, 1.0),
            text=f"{label}: {d['used']:,.0f} / {d['limit']:,} ({d['pct']:.1f}%)",
        )
    st.caption(
        "Stima locale basata sulle regole di pesatura Open-Meteo. "
        "Il limite è per indirizzo IP e potrebbe essere condiviso."
    )


# --------------------------------------------------------------------------
# Selezione località
# --------------------------------------------------------------------------
with st.form("ricerca"):
    query = st.text_input("Cerca una località", "Milano")
    submitted = st.form_submit_button("Cerca")

if "results_geo" not in st.session_state:
    st.session_state.results_geo = cached_geocode("Milano")
if submitted:
    st.session_state.results_geo = cached_geocode(query)

results_geo = st.session_state.results_geo
if not results_geo:
    st.warning("Nessuna località trovata.")
    st.stop()

labels = [f"{r['name']} ({r.get('admin1', '')}, {r['country_code']})" for r in results_geo]
idx = st.selectbox("Risultati", range(len(results_geo)), format_func=lambda i: labels[i])
loc = results_geo[idx]


# --------------------------------------------------------------------------
# Storico
# --------------------------------------------------------------------------
try:
    df = load_history(loc["latitude"], loc["longitude"])
except RuntimeError as e:
    st.error(str(e))
    st.stop()

st.caption(
    f"{len(df):,} giorni di dati per {loc['name']} "
    f"({loc['latitude']:.3f}, {loc['longitude']:.3f}, {loc.get('elevation', '?')} m slm) — "
    f"dal {df['time'].min():%Y-%m-%d} al {df['time'].max():%Y-%m-%d}"
)

col1, col2 = st.columns(2)
with col1:
    date = st.date_input("Giorno di interesse")
with col2:
    window = st.slider("Finestra ± giorni", 0, 21, 10)

trend = add_derived(day_across_years(df, date.month, date.day, window))

if trend.empty:
    st.warning("Nessun anno con finestra completa. Prova a ridurre la finestra.")
    st.stop()


# --------------------------------------------------------------------------
# Helper per i pannelli
# --------------------------------------------------------------------------
def panel(col, var: str, label: str, color: str, unit: str,
          yrange=None, trendline: str | None = None):
    """Scatter di una variabile per anno. Con trendline='ols' aggiunge la
    retta di regressione e una metrica con la pendenza per decennio."""
    fig = px.scatter(
        trend, x="year", y=var,
        trendline=trendline,
        color_discrete_sequence=[color],
        labels={var: unit, "year": "Anno"},
        title=label,
    )
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0), height=340)
    if yrange is not None:
        fig.update_yaxes(range=yrange)
    col.plotly_chart(fig, use_container_width=True)

    if trendline is None:
        return

    res = px.get_trendline_results(fig)
    if len(res):
        fit = res.iloc[0]["px_fit_results"]
        col.metric(
            label=f"{label} — trend",
            value=f"{fit.params[1] * 10:+.2f} {unit}/decennio",
            help=f"p-value = {fit.pvalues[1]:.1e} · R² = {fit.rsquared:.3f} · n = {int(fit.nobs)}",
        )


# --------------------------------------------------------------------------
# Temperature (con fit)
# --------------------------------------------------------------------------
st.subheader(f"Temperature attorno al {date.day}/{date.month} (±{window} gg) — {loc['name']}")

TEMP_VARS = {
    "temperature_2m_min": ("T min", "#4A90D9"),
    "temperature_2m_mean": ("T media", "#7B7B7B"),
    "temperature_2m_max": ("T max", "#D9534F"),
}

ymin = trend[list(TEMP_VARS)].min().min() - 1
ymax = trend[list(TEMP_VARS)].max().max() + 1

cols = st.columns(3)
for col, (var, (label, color)) in zip(cols, TEMP_VARS.items()):
    panel(col, var, label, color, "°C", yrange=[ymin, ymax], trendline="ols")

st.subheader("Escursione termica (DTR)")
panel(st.container(), "dtr", "T max − T min", "#7A5195", "°C", trendline="ols")


# --------------------------------------------------------------------------
# Precipitazioni (senza fit: accumuli a barre + diagnostiche)
# --------------------------------------------------------------------------
st.subheader(f"Precipitazioni — totale sulla finestra ±{window} gg")

precip_long = trend.melt(
    id_vars="year",
    value_vars=["rain_sum", "snow_mm"],
    var_name="fase",
    value_name="mm",
)
precip_long["fase"] = precip_long["fase"].map(
    {"rain_sum": "Pioggia", "snow_mm": "Neve (mm equivalenti)"}
)

fig = px.bar(
    precip_long, x="year", y="mm",
    color="fase",
    color_discrete_map={"Pioggia": "#2E86AB", "Neve (mm equivalenti)": "#8ECAE6"},
    labels={"mm": "mm", "year": "Anno", "fase": ""},
)
fig.update_layout(
    barmode="stack",
    height=420,
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
)
st.plotly_chart(fig, use_container_width=True)

cols = st.columns(2)
panel(cols[0], "snow_share", "Quota nevosa", "#8ECAE6", "%")
panel(cols[1], "intensity", "Intensità media", "#023047", "mm/h")


with st.expander("Dati aggregati"):
    st.dataframe(trend, use_container_width=True)