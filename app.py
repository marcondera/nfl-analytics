import streamlit as st
import pandas as pd
import requests
import re
from io import StringIO
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

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

MONTHS_PT = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
    7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"
}

def format_date_ptbr(date_str):
    try:
        dt = datetime.fromisoformat(date_str.split("T")[0]) if "T" in date_str else datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day:02d} {MONTHS_PT[dt.month]} {dt.year}"
    except Exception:
        return date_str

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_team_display_name(abbr):
    return PFR_NAME_MAP_REVERSE.get(abbr, abbr)

@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse(year):
    try:
        response = requests.get(NFLVERSE_GAMES_URL, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        df_year['home_score'] = pd.to_numeric(df_year['home_score'], errors='coerce').fillna(0).astype(int)
        df_year['away_score'] = pd.to_numeric(df_year['away_score'], errors='coerce').fillna(0).astype(int)
        df_year = df_year[(df_year['home_score'] > 0) | (df_year['away_score'] > 0)].copy()
        if df_year.empty:
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
                return pd.Series([None] * 10)
            if home_score >= away_score:
                winner_abbr, winner_pts = home_team, home_score
                loser_abbr, loser_pts = away_team, away_score
            else:
                winner_abbr, winner_pts = away_team, away_score
                loser_abbr, loser_pts = home_team, home_score
            return pd.Series([
                int(row['week']),
                row.get('gameday', ''),
                winner_abbr,
                winner_pts,
                loser_abbr,
                loser_pts,
                row.get('home_team', ''),
                row.get('away_team', ''),
                row.get('venue', ''),
                row.get('season', '')
            ])
        df_results = df_year.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Raw', 'Winner_Abbr', 'Winner_Pts', 'Loser_Abbr', 'Loser_Pts', 'Home_Abbr', 'Away_Abbr', 'Venue', 'Season']
        df_results = df_results.dropna(subset=['Winner_Abbr', 'Week'])
        df_results['Date_Full'] = df_results['Date_Raw'].apply(lambda d: format_date_ptbr(str(d)) if d else '')
        df_results['Winner_PFR'] = df_results['Winner_Abbr'].apply(get_team_display_name)
        df_results['Loser_PFR'] = df_results['Loser_Abbr'].apply(get_team_display_name)
        df_results['Week'] = pd.to_numeric(df_results['Week'], errors='coerce').astype('Int64')
        df_results = df_results.sort_values(by=['Week', 'Date_Full'])
        return df_results.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_live_events_from_espn():
    try:
        response = requests.get(API_URL_SCOREBOARD, timeout=8)
        response.raise_for_status()
        data = response.json()
        week_name = data.get('week', {}).get('text', '')
        current_week = int(re.search(r'\d+', week_name).group()) if re.search(r'\d+', week_name) else None
        return current_week, data.get('events', [])
    except Exception:
        return None, []

def calculate_standings(df_games):
    standings = {abbr: {'W': 0, 'L': 0, 'T': 0} for abbr in TEAM_CONFERENCE_DIVISION_MAP.keys()}
    for _, row in df_games.iterrows():
        w = row['Winner_Abbr']
        l = row['Loser_Abbr']
        wp = int(row['Winner_Pts'])
        lp = int(row['Loser_Pts'])
        if w in standings and l in standings:
            if wp > lp:
                standings[w]['W'] += 1
                standings[l]['L'] += 1
            elif wp == lp:
                standings[w]['T'] += 1
                standings[l]['T'] += 1
    df = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Abbr'})
    df['Team'] = df['Abbr'].apply(get_team_display_name)
    df['Conf'] = df['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('conf', 'N/A'))
    df['Div'] = df['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('div', 'N/A'))
    df = df[df['Conf'] != 'N/A'].copy()
    df['GP'] = df['W'] + df['L'] + df['T']
    df['PCT'] = df.apply(lambda r: (r['W'] + 0.5 * r['T']) / r['GP'] if r['GP'] > 0 else 0.0, axis=1)
    df['PCT_Str'] = df['PCT'].map('{:.3f}'.format)
    df = df.sort_values(by=['Conf', 'PCT', 'W'], ascending=[True, False, False]).reset_index(drop=True)
    df['Rank'] = df.groupby('Conf')['PCT'].rank(method='dense', ascending=False).astype(int)
    return df

def standings_card(df_conf, conf_name):
    df_conf = df_conf.copy().sort_values(by=['PCT', 'W'], ascending=[False, False])
    df_conf_display = df_conf[['Rank', 'Team', 'Abbr', 'W', 'L', 'T', 'PCT_Str']].rename(columns={
        'Rank': 'Pos', 'Abbr': 'Sigla', 'W': 'V', 'L': 'D', 'T': 'E', 'PCT_Str': 'PCT'
    })
    return df_conf_display

def wins_by_division_chart(df_standings):
    df = df_standings.groupby(['Conf', 'Div']).agg({'W': 'sum'}).reset_index()
    fig = px.bar(df, x='Div', y='W', color='Conf', barmode='group', title='Vitórias por Divisão')
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig

def weekly_progression(df_games, teams):
    weeks = sorted(df_games['Week'].unique())
    data = []
    for team in teams:
        team_wins = []
        for w in weeks:
            wk = df_games[df_games['Week'] == w]
            wins = 0
            for _, r in wk.iterrows():
                if r['Winner_Abbr'] == team:
                    wins += 1
            team_wins.append(wins)
        data.append({'team': team, 'wins': team_wins})
    fig = go.Figure()
    for d in data:
        fig.add_trace(go.Scatter(x=weeks, y=d['wins'], mode='lines+markers', name=get_team_display_name(d['team'])))
    fig.update_layout(title='Evolução Semanal de Vitórias (por time selecionado)', xaxis_title='Semana', yaxis_title='Vitórias na Semana', margin=dict(l=10, r=10, t=40, b=10))
    return fig

def total_wins_leaderboard(df_standings, top_n=10):
    df = df_standings.copy().sort_values(by=['W', 'PCT'], ascending=[False, False]).head(top_n)
    return df[['Team', 'Abbr', 'W', 'L', 'T', 'PCT_Str']].rename(columns={'PCT_Str': 'PCT'})

def inject_style():
    css = """
    <style>
    .pfr-root { font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; color: #212529; }
    .pfr-container { padding: 12px; border-radius: 12px; background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%); border: 1px solid #eef2f6; box-shadow: 0 6px 18px rgba(16,24,40,0.04); }
    .pfr-title { font-size: 20px; font-weight: 700; margin-bottom: 6px; color: #0f172a; }
    .pfr-sub { font-size: 13px; color: #475569; margin-bottom: 12px; }
    .pfr-small { font-size: 12px; color: #6b7280; }
    .pfr-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .pfr-card { padding: 12px; border-radius: 10px; background: #fff; border: 1px solid #eef2f6; box-shadow: 0 4px 12px rgba(2,6,23,0.04); }
    .pfr-standings-table th, .pfr-standings-table td { padding: 6px 8px; text-align: left; }
    .pfr-standings-table th { font-weight: 700; font-size: 12px; color:#0f172a; background: transparent; border-bottom: none; }
    .pfr-standings-table td { font-size: 13px; color: #0f172a; }
    .pfr-highlight { color: #0ea5a4; font-weight: 700; }
    .pfr-muted { color: #64748b; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

inject_style()

inject_css_scoreboard = """
<style>
.pfr-root .scoreboard-card {
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 12px;
    box-shadow: 0 6px 15px rgba(0,0,0,0.06);
    transition: transform 0.15s;
    background: #fff;
    border: 1px solid #eef2f6;
}
.pfr-root .scoreboard-card:hover { transform: translateY(-4px); }
.pfr-root .game-layout { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.pfr-root .team-info { display:flex; flex-direction:column; align-items:center; width:28%; min-width:80px; }
.pfr-root .team-info img { width:48px; height:48px; border-radius:50%; box-shadow: 0 2px 8px rgba(2,6,23,0.05); }
.pfr-root .score-container { display:flex; align-items:center; justify-content:center; gap:8px; min-width:120px; }
.pfr-root .score-winner { font-size:1.9rem; font-weight:800; color:#0ea5a4; }
.pfr-root .score-loser { font-size:1.6rem; font-weight:600; color:#94a3b8; }
.pfr-root .vs-text { font-weight:800; color:#475569; }
.pfr-root .status-final { text-align:center; margin-top:8px; font-weight:700; color:#10b981; }
.pfr-root .game-date { font-size:12px; color:#64748b; margin-bottom:8px; text-align:center; }
</style>
"""
st.markdown(inject_css_scoreboard, unsafe_allow_html=True)

inject_css_small = """
<style>
.stButton>button { border-radius: 8px; }
</style>
"""
st.markdown(inject_css_small, unsafe_allow_html=True)

historical_data = load_historical_events_from_nflverse(CURRENT_PFR_YEAR)
current_week_espn, live_events = load_live_events_from_espn()
if historical_data.empty:
    st.error("Não foi possível carregar dados históricos (NFLverse). Verifique a conexão ou a fonte.")
    st.stop()

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<div class="pfr-root"><div class="pfr-title">🏈 Dashboard Histórico — Estatísticas & Gráficos</div><div class="pfr-sub">Visão consolidada da temporada, com gráficos evolutivos e ranking por conferência.</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="pfr-root pfr-card"><div style="font-weight:800">Temporada</div><div class="pfr-small">Regular {CURRENT_PFR_YEAR}</div><hr style="opacity:.06" /><div class="pfr-small">Jogos processados:<br><span class="pfr-highlight">{len(historical_data)}</span></div></div>', unsafe_allow_html=True)

st.markdown("---")

col_left, col_center, col_right = st.columns([0.12, 3.7, 0.12])
with col_center:
    st.header(f"🗓️ Placar - Última Semana Jogada")
    max_week = int(historical_data['Week'].max())
    display_week = current_week_espn if current_week_espn and current_week_espn in historical_data['Week'].unique() else max_week
    st.markdown(f"<div class='pfr-root pfr-sub'>Mostrando resultados da semana <span class='pfr-highlight'>{display_week}</span></div>", unsafe_allow_html=True)
    games_list = historical_data[historical_data['Week'] == display_week][['Date_Full', 'Winner_Abbr', 'Loser_Abbr', 'Winner_Pts', 'Loser_Pts']].to_dict('records')
    cols_per_row = 3
    for i in range(0, len(games_list), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < len(games_list):
                g = games_list[idx]
                game_html = f"""
                <div class="pfr-root">
                  <div class="scoreboard-card pfr-card">
                    <div class="game-date">🗓️ {g['Date_Full']}</div>
                    <div class="game-layout">
                      <div class="team-info">
                        <img src="{get_logo_url(g['Winner_Abbr'])}" alt="">
                        <strong>{g['Winner_Abbr']}</strong>
                      </div>
                      <div class="score-container">
                        <div class="score-winner">{int(g['Winner_Pts'])}</div>
                        <div class="vs-text">VS</div>
                        <div class="score-loser">{int(g['Loser_Pts'])}</div>
                      </div>
                      <div class="team-info">
                        <img src="{get_logo_url(g['Loser_Abbr'])}" alt="">
                        <strong>{g['Loser_Abbr']}</strong>
                      </div>
                    </div>
                    <div class="status-final">• FINALIZADO</div>
                  </div>
                </div>
                """
                with cols[j]:
                    st.markdown(game_html, unsafe_allow_html=True)

st.markdown("---")

standings = calculate_standings(historical_data)

st.header("🏆 Classificação da Temporada")
afc_df = standings[standings['Conf'] == 'AFC']
nfc_df = standings[standings['Conf'] == 'NFC']

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("AFC")
    df_afc_display = standings_card(afc_df, 'AFC')
    st.table(df_afc_display.style.hide_index())
with col_b:
    st.subheader("NFC")
    df_nfc_display = standings_card(nfc_df, 'NFC')
    st.table(df_nfc_display.style.hide_index())

st.markdown("---")

st.header("📊 Painel de Estatísticas")
stat_col1, stat_col2 = st.columns([2, 3])

with stat_col1:
    st.markdown('<div class="pfr-root pfr-title">Vitórias por Divisão</div>', unsafe_allow_html=True)
    fig_div = wins_by_division_chart(standings)
    st.plotly_chart(fig_div, use_container_width=True)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    st.markdown('<div class="pfr-root pfr-title">Top - Total de Vitórias</div>', unsafe_allow_html=True)
    top_leaders = total_wins_leaderboard(standings, top_n=8)
    st.dataframe(top_leaders.rename(columns={'Team': 'Time', 'Abbr': 'Sigla', 'W': 'V', 'L': 'D', 'T': 'E', 'PCT_Str': 'PCT'}), use_container_width=True, hide_index=True)

with stat_col2:
    st.markdown('<div class="pfr-root pfr-title">Evolução Semanal — Times</div>', unsafe_allow_html=True)
    all_teams = sorted(list(standings['Abbr'].unique()))
    selected_teams = st.multiselect("Selecione até 4 times para ver evolução semanal:", options=all_teams, default=all_teams[:3], max_selections=4)
    if not selected_teams:
        st.info("Selecione ao menos um time.")
    else:
        fig_week = weekly_progression(historical_data, selected_teams)
        st.plotly_chart(fig_week, use_container_width=True)

st.markdown("---")

st.header("🗂️ Histórico de Jogos (por Semana)")
weeks = sorted(historical_data['Week'].unique())
selected_week = st.selectbox("Selecione a semana", weeks, index=len(weeks)-1, key="hist_week")
df_week = historical_data[historical_data['Week'] == selected_week].copy()
if df_week.empty:
    st.info("Nenhum jogo encontrado para essa semana.")
else:
    cards = []
    for idx, r in df_week.iterrows():
        cards.append({
            "data": r['Date_Full'],
            "winner": r['Winner_PFR'],
            "w_abbr": r['Winner_Abbr'],
            "w_pts": int(r['Winner_Pts']),
            "loser": r['Loser_PFR'],
            "l_abbr": r['Loser_Abbr'],
            "l_pts": int(r['Loser_Pts']),
            "venue": r.get('Venue', '')
        })
    rows = st.columns(1)
    grid_cols = st.columns(3)
    for i, card in enumerate(cards):
        with grid_cols[i % 3]:
            html = f"""
            <div class="pfr-root pfr-card" style="padding:10px">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="font-weight:800">{card['data']}</div>
                <div class="pfr-small">{card['venue']}</div>
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;margin-top:12px">
                <div style="text-align:center">
                  <img src="{get_logo_url(card['w_abbr'])}" style="width:42px;height:42px;border-radius:50%"><div style="font-weight:700;margin-top:6px">{card['w_abbr']}</div>
                </div>
                <div style="text-align:center">
                  <div style="font-size:20px;font-weight:900;color:#0ea5a4">{card['w_pts']}</div>
                  <div style="font-weight:800;color:#475569">VS</div>
                  <div style="font-size:18px;font-weight:700;color:#94a3b8">{card['l_pts']}</div>
                </div>
                <div style="text-align:center">
                  <img src="{get_logo_url(card['l_abbr'])}" style="width:42px;height:42px;border-radius:50%"><div style="font-weight:700;margin-top:6px">{card['l_abbr']}</div>
                </div>
              </div>
              <div style="margin-top:10px;font-size:12px;color:#64748b">{card['winner']} venceu {card['loser']}</div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

st.markdown("---")

st.header("🔎 Explorar Dados (Raw)")
if st.checkbox("Mostrar tabela completa de resultados (para análises)"):
    st.dataframe(historical_data[['Week', 'Date_Full', 'Winner_Abbr', 'Winner_Pts', 'Loser_Abbr', 'Loser_Pts', 'Venue']].rename(columns={
        'Week': 'Semana', 'Date_Full': 'Data', 'Winner_Abbr': 'Vencedor Sigla', 'Winner_Pts': 'Vencedor Pts',
        'Loser_Abbr': 'Perdedor Sigla', 'Loser_Pts': 'Perdedor Pts', 'Venue': 'Local'
    }), use_container_width=True)

st.markdown("---")

st.markdown('<div style="text-align:center;color:#94a3b8;font-size:12px">Desenvolvido — Visual leve e consistente com os cards do placar • Dados: NFLverse + ESPN</div>', unsafe_allow_html=True)
