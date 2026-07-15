import plotly.express as px
import streamlit as st

from meteo.analysis import day_across_years
from meteo.client import fetch_daily_history, geocode

st.set_page_config(page_title="Meteo storico", layout="wide")
st.title("🌤️ Analisi meteo storica")

# --- Selezione località ---
query = st.text_input("Cerca una località", "Milano")
results = geocode(query) if query else []
if not results:
    st.stop()

labels = [f"{r['name']} ({r.get('admin1','')}, {r['country_code']})" for r in results]
idx = st.selectbox("Risultati", range(len(results)), format_func=lambda i: labels[i])
loc = results[idx]

# --- Download storico (cachato!) ---
@st.cache_data(show_spinner="Scarico lo storico 1940–oggi...")
def load_history(lat, lon):
    return fetch_daily_history(lat, lon)

df = load_history(loc["latitude"], loc["longitude"])
st.caption(f"{len(df):,} giorni di dati per {loc['name']}")

# --- Parametri ---
col1, col2 = st.columns(2)
with col1:
    date = st.date_input("Giorno di interesse")
with col2:
    window = st.slider("Finestra ± giorni", 0, 21, 10)

# --- Trend nel corso degli anni ---
trend = day_across_years(df, date.month, date.day, window)

fig = px.scatter(
    trend, x="year", y="temperature_2m_mean",
    trendline="ols",
    labels={"temperature_2m_mean": "T media (°C)", "year": "Anno"},
    title=f"T media attorno al {date.day}/{date.month} (±{window} gg), {loc['name']}",
)
st.plotly_chart(fig, use_container_width=True)

