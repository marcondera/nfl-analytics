import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import re
from io import StringIO

# ==============================
# CONFIGURAÇÕES INICIAIS
# ==============================
CURRENT_PFR_YEAR = 2025

st.set_page_config(
    page_title=f"🏈 NFL Dashboard {CURRENT_PFR_YEAR}",
    layout="wide",
    page_icon="🏈"
)

API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# ==============================
# MAPAS E CONSTANTES
# ==============================
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

PFR_NAME_MAP_REVERSE = {
    'SF': '49ers', 'BUF': 'Bills', 'ATL': 'Falcons', 'BAL': 'Ravens', 'CAR': 'Panthers',
    'CIN': 'Bengals', 'CHI': 'Bears', 'CLE': 'Browns', 'DAL': 'Cowboys', 'DEN': 'Broncos',
    'DET': 'Lions', 'GB': 'Packers', 'HOU': 'Texans', 'IND': 'Colts', 'JAX': 'Jaguars',
    'KC': 'Chiefs', 'LAC': 'Chargers', 'LAR': 'Rams', 'LV': 'Raiders', 'MIA': 'Dolphins',
    'MIN': 'Vikings', 'NE': 'Patriots', 'NO': 'Saints', 'NYG': 'Giants', 'NYJ': 'Jets',
    'PHI': 'Eagles', 'PIT': 'Steelers', 'SEA': 'Seahawks', 'TB': 'Buccaneers', 'TEN': 'Titans',
    'ARI': 'Cardinals', 'WSH': 'Commanders'
}

TEAM_CONFERENCE_DIVISION_MAP = {
    'BUF': {'conf': 'AFC', 'div': 'East'}, 'MIA': {'conf': 'AFC', 'div': 'East'}, 'NE': {'conf': 'AFC', 'div': 'East'}, 'NYJ': {'conf': 'AFC', 'div': 'East'},
    'BAL': {'conf': 'AFC', 'div': 'North'}, 'CIN': {'conf': 'AFC', 'div': 'North'}, 'CLE': {'conf': 'AFC', 'div': 'North'}, 'PIT': {'conf': 'AFC', 'div': 'North'},
    'HOU': {'conf': 'AFC', 'div': 'South'}, 'IND': {'conf': 'AFC', 'div': 'South'}, 'JAX': {'conf': 'AFC', 'div': 'South'}, 'TEN': {'conf': 'AFC', 'div': 'South'},
    'DEN': {'conf': 'AFC', 'div': 'West'}, 'KC': {'conf': 'AFC', 'div': 'West'}, 'LV': {'conf': 'AFC', 'div': 'West'}, 'LAC': {'conf': 'AFC', 'div': 'West'},
    'DAL': {'conf': 'NFC', 'div': 'East'}, 'NYG': {'conf': 'NFC', 'div': 'East'}, 'PHI': {'conf': 'NFC', 'div': 'East'}, 'WSH': {'conf': 'NFC', 'div': 'East'},
    'CHI': {'conf': 'NFC', 'div': 'North'}, 'DET': {'conf': 'NFC', 'div': 'North'}, 'GB': {'conf': 'NFC', 'div': 'North'}, 'MIN': {'conf': 'NFC', 'div': 'North'},
    'ATL': {'conf': 'NFC', 'div': 'South'}, 'CAR': {'conf': 'NFC', 'div': 'South'}, 'NO': {'conf': 'NFC', 'div': 'South'}, 'TB': {'conf': 'NFC', 'div': 'South'},
    'ARI': {'conf': 'NFC', 'div': 'West'}, 'LAR': {'conf': 'NFC', 'div': 'West'}, 'SF': {'conf': 'NFC', 'div': 'West'}, 'SEA': {'conf': 'NFC', 'div': 'West'}
}

# ==============================
# FUNÇÕES AUXILIARES
# ==============================
def get_logo_url(abbr):
    a = LOGO_MAP.get(abbr.upper(), abbr.lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{a}.png"

def get_team_display_name(abbr):
    return PFR_NAME_MAP_REVERSE.get(abbr, abbr)

# ==============================
# CSS PERSONALIZADO
# ==============================
def inject_css():
    st.markdown("""
    <style>
    .scoreboard-card {
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
        background: #fff;
        border: 1px solid #eaeaea;
        box-shadow: 0 3px 8px rgba(0,0,0,0.05);
    }
    .team-info { text-align: center; }
    .team-info img { width: 48px; height: 48px; border-radius: 50%; }
    .score { font-size: 2em; font-weight: bold; }
    .status { font-size: 0.85em; color: #198754; margin-top: 8px; }
    </style>
    """, unsafe_allow_html=True)

# ==============================
# FUNÇÕES DE CARGA DE DADOS
# ==============================
@st.cache_data(ttl=3600)
def load_historical(year):
    try:
        r = requests.get(NFLVERSE_GAMES_URL, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text))
        df = df[(df['season'] == year) & (df['game_type'] == 'REG')]
        df['home_score'] = pd.to_numeric(df['home_score'], errors='coerce')
        df['away_score'] = pd.to_numeric(df['away_score'], errors='coerce')

        df = df.dropna(subset=['home_team', 'away_team'])
        df['Week'] = pd.to_numeric(df['week'], errors='coerce').astype('Int64')

        results = []
        for _, row in df.iterrows():
            home, away = row['home_team'], row['away_team']
            hs, as_ = row['home_score'], row['away_score']

            if pd.isna(hs) or pd.isna(as_):
                continue  # ignora jogo sem placar

            winner, loser = (home, away) if hs >= as_ else (away, home)
            winner_pts, loser_pts = (hs, as_) if hs >= as_ else (as_, hs)
            results.append({
                "Week": int(row['week']),
                "Date_Full": f"{row['gameday']} {year}",
                "Winner_Abbr": winner,
                "Loser_Abbr": loser,
                "Winner_Pts": int(winner_pts),
                "Loser_Pts": int(loser_pts)
            })

        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Erro ao carregar dados históricos: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_live():
    try:
        r = requests.get(API_URL_SCOREBOARD, timeout=10)
        data = r.json()
        week = data.get('week', {}).get('number', None)
        return week, data.get('events', [])
    except Exception:
        return None, []

# ==============================
# EXIBIÇÃO DE JOGOS
# ==============================
def display_future_games(events):
    if not events:
        st.info("Nenhum jogo futuro encontrado nesta semana.")
        return
    for ev in events:
        comps = ev.get("competitions", [{}])[0]
        teams = comps.get("competitors", [])
        if len(teams) == 2:
            home = teams[0]
            away = teams[1]
            st.markdown(f"📅 {home['team']['displayName']} vs {away['team']['displayName']} - {ev.get('status', {}).get('type', {}).get('description', '')}")

def display_scoreboard(df, week, live_events):
    inject_css()
    if df.empty:
        st.warning("Nenhum dado histórico disponível.")
        display_future_games(live_events)
        return

    dfw = df[df['Week'] == week]
    if dfw.empty:
        st.info(f"Semana {week} ainda sem resultados completos.")
        display_future_games(live_events)
        return

    st.header(f"🗓️ Semana {week}")
    cols = st.columns(3)
    for i, row in enumerate(dfw.itertuples(), start=0):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="scoreboard-card">
              <div class="team-info"><img src="{get_logo_url(row.Winner_Abbr)}"><br><b>{row.Winner_Abbr}</b></div>
              <div class="score">{row.Winner_Pts} - {row.Loser_Pts}</div>
              <div class="team-info"><img src="{get_logo_url(row.Loser_Abbr)}"><br><b>{row.Loser_Abbr}</b></div>
              <div class="status">FINALIZADO</div>
            </div>
            """, unsafe_allow_html=True)

# ==============================
# APP PRINCIPAL
# ==============================
st.title(f"🏈 Dashboard NFL {CURRENT_PFR_YEAR}")
st.markdown("Acompanhe os resultados e classificações atualizados em tempo real (ESPN + NFLverse).")
st.divider()

hist = load_historical(CURRENT_PFR_YEAR)
week_now, live_events = load_live()

if week_now is None:
    st.error("Falha ao obter semana atual via API ESPN.")
else:
    display_scoreboard(hist, week_now, live_events)
