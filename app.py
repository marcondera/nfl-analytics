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

def inject_custom_css():
    st.markdown("""
    <style>
    .pfr-root .scoreboard-card {
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08);
        background: #ffffff;
        border: 1px solid #e9ecef;
    }
    .pfr-root .team-info img {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        margin-bottom: 5px;
        background: #f8f9fa;
        padding: 2px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .pfr-root .score-winner {
        font-size: 2.4em; color: #007bff; font-weight: 800;
    }
    .pfr-root .score-loser {
        font-size: 2.0em; color: #adb5bd;
    }
    .pfr-root .game-date { font-size: 0.8em; color: #6c757d; margin-bottom: 8px; }
    .pfr-root .status-final { font-size: 0.85em; color: #198754; font-weight: bold; margin-top: 6px; }
    </style>
    """, unsafe_allow_html=True)

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_team_display_name(abbr):
    return PFR_NAME_MAP_REVERSE.get(abbr, abbr)

@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse(year):
    st.info(f"⏳ Carregando dados históricos do NFLverse para {year}...")
    try:
        response = requests.get(NFLVERSE_GAMES_URL)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        df_year['home_score'] = pd.to_numeric(df_year['home_score'], errors='coerce').fillna(0)
        df_year['away_score'] = pd.to_numeric(df_year['away_score'], errors='coerce').fillna(0)
        df_year = df_year[(df_year['home_score'] > 0) | (df_year['away_score'] > 0)]
        if df_year.empty:
            st.warning(f"Nenhum jogo encontrado para {year}.")
            return pd.DataFrame()

        def standardize_abbr(abbr):
            if abbr in ['WAS', 'WSH']: return 'WSH'
            return abbr if abbr in TEAM_CONFERENCE_DIVISION_MAP else None

        def calculate_result(row):
            home_score, away_score = int(row['home_score']), int(row['away_score'])
            home_team, away_team = standardize_abbr(row['home_team']), standardize_abbr(row['away_team'])
            if not home_team or not away_team: return pd.Series([None]*8)
            if home_score >= away_score:
                w, wp, l, lp = home_team, home_score, away_team, away_score
            else:
                w, wp, l, lp = away_team, away_score, home_team, home_score
            winner_name, loser_name = get_team_display_name(w), get_team_display_name(l)

            # 🗓️ Formatar data no estilo pt-BR
            try:
                date_fmt = datetime.strptime(str(row['gameday']), "%Y-%m-%d").strftime("%d %b %Y").lower()
            except Exception:
                date_fmt = row['gameday']

            return pd.Series([row['week'], date_fmt, winner_name, w, wp, loser_name, l, lp])

        df_results = df_year.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts']
        df_results = df_results.dropna(subset=['Winner_Abbr'])
        st.success(f"✅ Dados carregados com sucesso ({df_results['Week'].max()} semanas).")
        return df_results
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_live_events_from_espn():
    try:
        data = requests.get(API_URL_SCOREBOARD).json()
        week_name = data.get('week', {}).get('text', 'Semana Desconhecida')
        current_week = int(re.search(r'\d+', week_name).group()) if re.search(r'\d+', week_name) else None
        return current_week, data.get('events', [])
    except Exception:
        return None, []

def calculate_standings(df_games):
    standings = {abbr: {'W': 0, 'L': 0, 'T': 0} for abbr in TEAM_CONFERENCE_DIVISION_MAP}
    for _, g in df_games.iterrows():
        w, l, wp, lp = g['Winner_Abbr'], g['Loser_Abbr'], g['Winner_Pts'], g['Loser_Pts']
        if w in standings and l in standings:
            if wp > lp: standings[w]['W'] += 1; standings[l]['L'] += 1
            elif wp == lp: standings[w]['T'] += 1; standings[l]['T'] += 1
    df = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index':'Abbr'})
    df['Conf'] = df['Abbr'].map(lambda x: TEAM_CONFERENCE_DIVISION_MAP[x]['conf'])
    df['Div'] = df['Abbr'].map(lambda x: TEAM_CONFERENCE_DIVISION_MAP[x]['div'])
    df['GP'] = df['W']+df['L']+df['T']
    df['PCT'] = df.apply(lambda r:(r['W']+0.5*r['T'])/r['GP'] if r['GP']>0 else 0, axis=1)
    df['PCT_Str'] = df['PCT'].map('{:.3f}'.format)
    return df

def display_standings(df, conf):
    st.subheader(f"🏆 {conf}")
    conf_df = df[df['Conf']==conf]
    for div in sorted(conf_df['Div'].unique()):
        st.markdown(f"### Divisão {div}")
        div_df = conf_df[conf_df['Div']==div].copy()
        div_df['Time'] = div_df['Abbr'].map(get_team_display_name)
        div_df = div_df.sort_values(['PCT','W'],ascending=[False,False])
        st.dataframe(
            div_df[['Time','Abbr','W','L','T','PCT_Str']].rename(columns={'Abbr':'Sigla','W':'V','L':'D','T':'E','PCT_Str':'PCT'}),
            hide_index=True,
            use_container_width=True
        )

def display_scoreboard(df, current_week):
    if df.empty:
        st.info("Nenhum jogo encontrado.")
        return
    week = current_week or df['Week'].max()
    st.header(f"🗓️ Semana {week}")
    df_show = df[df['Week']==week]
    cols = st.columns(3)
    for i, (_, g) in enumerate(df_show.iterrows()):
        html = f"""
        <div class="pfr-root">
          <div class="scoreboard-card">
            <div class="game-date">🗓️ {g['Date_Full']}</div>
            <div class="game-layout" style="display:flex;align-items:center;justify-content:space-between;">
              <div class="team-info">
                <img src="{get_logo_url(g['Winner_Abbr'])}">
                <strong>{g['Winner_Abbr']}</strong>
              </div>
              <div class="score-container" style="text-align:center;">
                <span class="score-winner">{g['Winner_Pts']}</span>
                <span class="vs-text">×</span>
                <span class="score-loser">{g['Loser_Pts']}</span>
              </div>
              <div class="team-info">
                <img src="{get_logo_url(g['Loser_Abbr'])}">
                <strong>{g['Loser_Abbr']}</strong>
              </div>
            </div>
            <div class="status-final">Finalizado</div>
          </div>
        </div>
        """
        with cols[i%3]:
            st.markdown(html, unsafe_allow_html=True)

# ========================
# Execução principal
# ========================
inject_custom_css()
historical_data = load_historical_events_from_nflverse(CURRENT_PFR_YEAR)
current_week_espn, live_events = load_live_events_from_espn()

st.title(f"🏈 Dashboard Histórico NFL {CURRENT_PFR_YEAR}")
st.divider()

if historical_data.empty:
    st.error("Sem dados.")
else:
    display_scoreboard(historical_data, current_week_espn)
    st.divider()
    standings_data = calculate_standings(historical_data)
    st.header("🏆 Classificação da Temporada Regular")
    col1, col2 = st.columns(2)
    with col1:
        display_standings(standings_data, 'AFC')
    with col2:
        display_standings(standings_data, 'NFC')

    st.header("📜 Explorar Semanas Anteriores")
    all_weeks = sorted(historical_data['Week'].unique())
    selected_week = st.selectbox("Escolha uma semana:", options=all_weeks, index=len(all_weeks)-1)
    df_week = historical_data[historical_data['Week']==selected_week]
    df_week['Placar Final'] = df_week.apply(
        lambda r: f"🏆 **{r['Winner_PFR']}** ({int(r['Winner_Pts'])}) x {int(r['Loser_Pts'])} {r['Loser_PFR']}",
        axis=1
    )
    df_final = df_week[['Date_Full','Placar Final']].rename(columns={'Date_Full':'Data'})
    st.dataframe(df_final, hide_index=True, use_container_width=True)
