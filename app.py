import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
from meteo.analysis import add_derived, day_across_years, smooth
from meteo.client import fetch_daily_history, geocode
from meteo.quota import usage
import plotly.io as pio

pio.templates["meteo"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E8EDF2", size=13),
    )
)
pio.templates.default = "plotly_dark+meteo"

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
if "results_geo" not in st.session_state:
    st.session_state.results_geo = []

with st.form("ricerca"):
    query = st.text_input(
        "Cerca una località",
        placeholder="Es. Milano, Livigno, Trieste...",
    )
    submitted = st.form_submit_button("Cerca")

if submitted:
    q = query.strip()
    st.session_state.results_geo = cached_geocode(q) if q else []
    if q and not st.session_state.results_geo:
        st.warning(f"Nessuna località trovata per «{q}».")

results_geo = st.session_state.results_geo
if not results_geo:
    if not submitted:
        st.info("Cerca una località per iniziare.")
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
def bars_with_smoother(container, df, var, label, color, unit,
                       yrange=None, ticksuffix="", color_by=None, color_label=""):
    """Barre = dato annuale, linea nera = media mobile 11 anni."""
    fig = go.Figure()

    marker = dict(color=color)
    if color_by is not None:
        marker = dict(
            color=df[color_by],
            colorscale="Blues",
            colorbar=dict(title=color_label, thickness=12),
        )

    fig.add_bar(x=df["year"], y=df[var], marker=marker, name=label, opacity=0.85)
    fig.add_scatter(
        x=df["year"], y=smooth(df[var]),
        mode="lines", name="Media mobile 11 anni",
        line=dict(color="#FFB703", width=2.5),
    )
    fig.update_layout(
        height=400,
        margin=dict(l=0, r=0, t=50, b=0),
        yaxis_title=unit,
        xaxis_title="Anno",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
        bargap=0.15,
    )
    if yrange is not None:
        fig.update_yaxes(range=yrange)
    if ticksuffix:
        fig.update_yaxes(ticksuffix=ticksuffix)
    container.plotly_chart(fig, use_container_width=True)

def panel(col, var: str, label: str, color: str, unit: str,
          yrange=None, trendline: str | None = None):
    """Scatter di una variabile per anno. Con trendline='ols'"""
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
# --------------------------------------------------------------------------
# Precipitazioni (senza fit: accumuli a barre + media mobile)
# --------------------------------------------------------------------------
st.subheader(f"Precipitazioni — totale sulla finestra ±{window} gg")

precip_long = trend.melt(
    id_vars="year", value_vars=["rain_sum", "snow_mm"],
    var_name="fase", value_name="mm",
)
precip_long["fase"] = precip_long["fase"].map(
    {"rain_sum": "Pioggia", "snow_mm": "Neve (mm equivalenti)"}
)

fig = px.bar(
    precip_long, x="year", y="mm", color="fase",
    color_discrete_map={"Pioggia": "#2E86AB", "Neve (mm equivalenti)": "#8ECAE6"},
    labels={"mm": "mm", "year": "Anno", "fase": ""},
)
fig.add_scatter(
    x=trend["year"], y=smooth(trend["precipitation_sum"]),
    mode="lines", name="Totale, media mobile 11 anni",
    line=dict(color="#FFB703", width=2.5),
)
fig.update_layout(
    barmode="stack",
    height=420,
    margin=dict(l=0, r=0, t=50, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    bargap=0.15,
)
st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------
# Fase della precipitazione
# --------------------------------------------------------------------------
st.subheader("Fase della precipitazione")

if trend["snow_share"].fillna(0).max() < 0.5:
    st.info(
        f"Nessuna nevicata nei {2 * window + 1} giorni attorno al "
        f"{date.day}/{date.month} in nessun anno della serie — normale per una data "
        "estiva o una località di pianura. Prova una data invernale o una località di quota."
    )
else:
    bars_with_smoother(
        st.container(), trend, "snow_share", "Quota nevosa", "#8ECAE6", "",
        yrange=[0, 100], ticksuffix="%",
        color_by="precipitation_sum", color_label="mm tot",
    )
    st.caption(
        "Altezza = % della precipitazione caduta come neve (in mm di acqua equivalente). "
        "**Intensità del colore = precipitazione totale**: le barre chiare sono anni "
        "quasi asciutti, dove la percentuale è dominata dal rumore. Gli anni senza "
        "precipitazione non compaiono."
    )


# --------------------------------------------------------------------------
# Intensità
# --------------------------------------------------------------------------
st.subheader("Intensità media")

if trend["intensity"].notna().sum() < 3:
    st.info("Troppi anni senza precipitazione per calcolare l'intensità.")
else:
    bars_with_smoother(
        st.container(), trend, "intensity", "mm per ora di pioggia", "#023047", "mm/h",
    )
    st.caption(
        "Millimetri totali diviso ore di precipitazione. Non definita negli anni "
        "senza pioggia, che quindi non compaiono."
    )


with st.expander("Dati aggregati"):
    st.dataframe(trend, use_container_width=True)
st.divider()

st.caption(
    f"**Fonte dati:** reanalysis ERA5 del Copernicus Climate Change Service / ECMWF, "
    f"via [Open-Meteo](https://open-meteo.com), licenza "
    f"[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). "
    f"Serie per {loc['name']} ({loc['latitude']:.3f}, {loc['longitude']:.3f}, "
    f"{loc.get('elevation', '?')} m slm) dal {df['time'].min():%d/%m/%Y} "
    f"al {df['time'].max():%d/%m/%Y}; ERA5 pubblica con ~5 giorni di ritardo.  \n"
    f"Una reanalysis non è una stazione meteorologica: è la ricostruzione modellistica "
    f"dello stato dell'atmosfera, vincolata alle osservazioni tramite assimilazione dati, "
    f"su una cella di griglia che contiene la località. La temperatura a 2 m è "
    f"direttamente vincolata dalle osservazioni al suolo; **la precipitazione no** — "
    f"è un prodotto del modello, con bias noti soprattutto in orografia complessa. "
    f"L'infittimento della rete osservativa (satelliti dal 1979) rende la serie "
    f"non omogenea nel tempo: i trend sui decenni più antichi sono meno solidi."
)