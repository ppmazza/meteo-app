# Meteo Storico

App Streamlit per esplorare lo storico meteo (dal 1979 a oggi) di una qualsiasi località, usando le API gratuite di [Open-Meteo](https://open-meteo.com/).

Cerca una città, scegli un giorno dell'anno e una finestra di ± giorni, e visualizza l'andamento di temperature, precipitazioni e loro fase (pioggia/neve) in quel periodo attraverso gli anni (con relative rette di trend e medie mobili).

## Funzionalità

- Ricerca geografica di una località (geocoding)
- Download dello storico giornaliero (temperature min/media/max, precipitazioni, pioggia, neve, ore di precipitazione) dal 2010 a oggi
- Analisi anno per anno sulla finestra di giorni scelta:
  - Temperature min/media/max, con trendline e stima della pendenza per decennio
  - Escursione termica giornaliera (DTR)
  - Precipitazioni totali (pioggia + neve equivalente) con media mobile a 11 anni
  - Fase della precipitazione (quota nevosa %)
  - Intensità media della pioggia (mm/h)
- Stima del consumo di chiamate API in sidebar (per minuto/ora/giorno), con blocco preventivo delle richieste che sforerebbero i limiti
- Cache su disco (Parquet, in `.cache/`) dello storico scaricato, oltre alla cache di sessione di Streamlit

## Requisiti

- Python >= 3.12, < 3.13
- [uv](https://docs.astral.sh/uv/) come gestore di pacchetti/ambienti (consigliato)

## Installazione

Con `uv` (usa automaticamente la versione di Python e le dipendenze definite in `pyproject.toml` / `uv.lock`):

```bash
uv sync
```

In alternativa, con `pip` in un virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas plotly pyarrow requests statsmodels streamlit
```

## Avvio dell'app

Con `uv`:

```bash
uv run streamlit run app.py
```

Oppure, con il virtualenv già attivato:

```bash
streamlit run app.py
```

L'app si apre automaticamente nel browser all'indirizzo `http://localhost:8501`.

## Struttura del progetto

```
app.py              # entry point Streamlit (UI)
meteo/
  client.py         # chiamate alle API Open-Meteo (geocoding + storico) e cache su disco
  analysis.py        # analisi dati (aggregazione su finestra di giorni, per anno)
  quota.py           # stima e registro locale del consumo di chiamate API
pyproject.toml       # dipendenze e configurazione progetto
.streamlit/
  config.toml       # tema dell'interfaccia
```

## Note

- Non è richiesta alcuna API key: Open-Meteo espone endpoint pubblici e gratuiti.
- Open-Meteo non espone header di rate limit: il modulo `meteo/quota.py` tiene un registro locale delle chiamate e ne stima il peso secondo le regole documentate da Open-Meteo. È una stima, non un dato ufficiale: il limite è per indirizzo IP e potrebbe essere condiviso con altri client sulla stessa rete.
- Lo storico giornaliero scaricato viene cachato su disco in formato Parquet (`.cache/`), oltre a essere cachato in sessione da Streamlit (`st.cache_data`), per evitare download ripetuti.
- I dati sono una reanalysis ERA5 (Copernicus Climate Change Service / ECMWF), non osservazioni dirette da stazione: pubblicano con ~5-6 giorni di ritardo e i trend sui decenni più antichi sono meno solidi per via dell'infittimento della rete osservativa satellitare dal 1979.