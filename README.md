# Meteo Storico

App Streamlit per esplorare lo storico meteo (dal 1940 a oggi) di una qualsiasi località, usando le API gratuite di [Open-Meteo](https://open-meteo.com/).

Cerca una città, scegli un giorno dell'anno e una finestra di ± giorni, e visualizza l'andamento della temperatura media in quel periodo attraverso gli anni (con relativa retta di trend).

## Funzionalità

- Ricerca geografica di una località (geocoding)
- Download dello storico giornaliero (temperature min/media/max, precipitazioni, vento) dal 1940 a oggi
- Analisi della temperatura media in una finestra di giorni attorno a una data, anno per anno
- Grafico interattivo con trendline

## Requisiti

- Python >= 3.14
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
pip install pandas plotly requests statsmodels streamlit
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
  client.py         # chiamate alle API Open-Meteo (geocoding + storico)
  analysis.py        # analisi dati (media su finestra di giorni, per anno)
pyproject.toml       # dipendenze e configurazione progetto
```

## Note

- Non è richiesta alcuna API key: Open-Meteo espone endpoint pubblici e gratuiti.
- I dati storici vengono cachati da Streamlit (`st.cache_data`) per evitare download ripetuti durante la sessione.