import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import re
import math
from io import StringIO

CURRENT_PFR_YEAR = 2025

st.set_page_config(page_title=f"🏈 NFL Dashboard {CURRENT_PFR_YEAR}", layout="wide", page_icon="🏈")

API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

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

def format_date_br(date_str):
    """Converte datas para formato brasileiro dd/mm/yyyy."""
    try:
        if isinstance(date_str, str):
            if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            elif re.match(r"\d{2} [A-Za-z]{3} \d{4}", date_str):
                return datetime.strptime(date_str, "%d %b %Y").strftime("%d/%m/%Y")
        return date_str
    except:
        return date_str

def inject_custom_css():
    SCOREBOARD_CSS = """
    <style>
    .pfr-root .scoreboard-card {
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s, box-shadow 0.2s;
        background: #ffffff;
        border: 1px solid #e9ecef;
    }
    .pfr-root .scoreboard-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
    }
    .pfr-root .game-layout {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .pfr-root .score-winner {
        font-family: 'Inter', sans-serif;
        font-size: 2.5em;
        font-weight: 900;
        color: #007bff;
        margin: 0;
        padding: 0 15px;
        line-height: 1;
    }
    .pfr-root .score-loser {
        font-family: 'Inter', sans-serif;
        font-size: 2.0em;
        font-weight: 500;
        color: #adb5bd;
        margin: 0;
        padding: 0 15px;
        line-height: 1;
    }
    .pfr-root .score-container {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-grow: 1;
        min-width: 120px;
    }
    .pfr-root .vs-text {
        font-size: 1.2em;
        font-weight: 700;
        color: #6c757d;
        margin: 0 5px;
    }
    .pfr-root .team-info {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        width: 30%;
        min-width: 80px;
    }
    .pfr-root .team-info img {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        margin-bottom: 5px;
        background: #f8f9fa;
        padding: 2px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    }
    .pfr-root .team-info strong {
        font-size: 1.0em;
        line-height: 1.2;
        color: #343a40;
    }
    .pfr-root .status-final {
        text-align: center;
        font-size: 0.85em;
        color: #198754;
        font-weight: bold;
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #f8f9fa;
    }
    .pfr-root .game-date {
        text-align: center;
        font-size: 0.8em;
        color: #6c757d;
        margin-bottom: 10px;
        border-bottom: 1px dashed #e9ecef;
        padding-bottom: 5px;
    }
    </style>
    """
    st.markdown(SCOREBOARD_CSS, unsafe_allow_html=True)

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_team_display_name(abbr):
    return PFR_NAME_MAP_REVERSE.get(abbr, abbr)

@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse(year):
    st.info(f"⏳ Tentando carregar dados históricos do NFLverse para a temporada: **{year}**.")
    try:
        response = requests.get(NFLVERSE_GAMES_URL)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        df_year['home_score'] = pd.to_numeric(df_year['home_score'], errors='coerce').fillna(0)
        df_year['away_score'] = pd.to_numeric(df_year['away_score'], errors='coerce').fillna(0)
        df_year = df_year[(df_year['home_score'] > 0) | (df_year['away_score'] > 0)].copy()
        if df_year.empty:
            st.warning(f"Nenhum jogo jogado encontrado no NFLverse para a temporada {year}. O placar estará vazio.")
            return pd.DataFrame()
        def standardize_abbr(abbr):
            if abbr in ['WAS', 'WSH']:
                return 'WSH'
            if abbr not in TEAM_CONFERENCE_DIVISION_MAP:
                return None
            return abbr
        def calculate_result(row):
            home_score = int(row['home_score'])
            away_score = int(row['away_score'])
            home_team = standardize_abbr(row['home_team'])
            away_team = standardize_abbr(row['away_team'])
            if home_team is None or away_team is None:
                return pd.Series([None] * 8)
            if home_score >= away_score:
                winner_abbr, winner_pts = home_team, home_score
                loser_abbr, loser_pts = away_team, away_score
            else:
                winner_abbr, winner_pts = away_team, away_score
                loser_abbr, loser_pts = home_team, home_score
            winner_name = get_team_display_name(winner_abbr)
            loser_name = get_team_display_name(loser_abbr)

            # ✅ Apenas conversão de data
            formatted_date = format_date_br(str(row['gameday']))

            return pd.Series([
                row['week'],
                f"{formatted_date}",
                winner_name,
                winner_abbr,
                winner_pts,
                loser_name,
                loser_abbr,
                loser_pts,
            ])
        df_results = df_year.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts']
        df_results = df_results.dropna(subset=['Winner_Abbr', 'Week'])
        df_results['Week'] = pd.to_numeric(df_results['Week'], errors='coerce').astype('Int64')
        return df_results
    except:
        return pd.DataFrame()

# --- restante do código idêntico ---
# Nenhuma modificação visual ou lógica feita abaixo
# (mantido 100% igual ao seu arquivo)
