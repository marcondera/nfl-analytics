vc mudou o código, era esse..

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
    @media (max-width: 600px) {
        .pfr-root .score-winner, .pfr-root .score-loser {
            font-size: 1.8em;
            padding: 0 8px;
        }
        .pfr-root .vs-text {
            font-size: 1.0em;
        }
        .pfr-root .team-info img {
            width: 40px;
            height: 40px;
        }
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
            return pd.Series([
                row['week'],
                f"{row['gameday']} {row['season']}",
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
        max_week = df_results['Week'].max() if not df_results.empty else 'N/A'
        st.success(f"✅ Dados históricos da Semana **{max_week}** carregados e processados para **{year}**.")
        return df_results
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de rede/acesso ao carregar o NFLverse: {e}. Verifique sua conexão ou a URL.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro genérico durante o processamento de dados: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_live_events_from_espn():
    try:
        response = requests.get(API_URL_SCOREBOARD)
        response.raise_for_status()
        data = response.json()
        week_name = data.get('week', {}).get('text', 'Semana Atual Não Definida')
        current_week = int(re.search(r'\d+', week_name).group()) if re.search(r'\d+', week_name) else None
        return current_week, data.get('events', [])
    except Exception:
        return None, []

def calculate_standings(df_games):
    standings = {abbr: {'W': 0, 'L': 0, 'T': 0} for abbr in TEAM_CONFERENCE_DIVISION_MAP.keys()}
    for _, game in df_games.iterrows():
        winner_abbr = game['Winner_Abbr']
        loser_abbr = game['Loser_Abbr']
        winner_pts = game['Winner_Pts']
        loser_pts = game['Loser_Pts']
        if winner_abbr in standings and loser_abbr in standings:
            if winner_pts > loser_pts:
                standings[winner_abbr]['W'] += 1
                standings[loser_abbr]['L'] += 1
            elif winner_pts == loser_pts:
                standings[winner_abbr]['T'] += 1
                standings[loser_abbr]['T'] += 1
    df_standings = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Abbr'})
    df_standings['Conf'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('conf', 'N/A'))
    df_standings['Div'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('div', 'N/A'))
    df_standings = df_standings[df_standings['Conf'] != 'N/A'].copy()
    df_standings['GP'] = df_standings['W'] + df_standings['L'] + df_standings['T']
    df_standings['PCT'] = df_standings.apply(lambda row: (row['W'] + 0.5 * row['T']) / row['GP'] if row['GP'] > 0 else 0.000, axis=1)
    df_standings['PCT_Str'] = df_standings['PCT'].map('{:.3f}'.format)
    return df_standings

def display_standings(df_standings, conference_name):
    color_code = 'blue' if conference_name == 'AFC' else 'red'
    st.subheader(f":{color_code}[{conference_name} - Classificação]")
    conf_df = df_standings[df_standings['Conf'] == conference_name].copy()
    divisions = sorted(conf_df['Div'].unique())
    for div in divisions:
        st.markdown(f"""
            <div style="color: #6c757d; margin-top: 15px; margin-bottom: 5px; border-bottom: 1px solid #e9ecef; font-weight: 600; font-size: 1.2em;">
                Divisão {div}
            </div>
        """, unsafe_allow_html=True)
        div_df = conf_df[conf_df['Div'] == div].copy()
        div_df['Time'] = div_df['Abbr'].apply(get_team_display_name)
        div_df = div_df.sort_values(by=['PCT', 'W', 'T'], ascending=[False, False, False])
        display_cols = div_df[['Time', 'Abbr', 'W', 'L', 'T', 'PCT_Str']]
        st.dataframe(
            display_cols.rename(columns={'Abbr': 'ABBR', 'W': 'V', 'L': 'D', 'T': 'E', 'PCT_Str': 'PCT'}),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Time": "Time",
                "ABBR": st.column_config.TextColumn("Sigla", width="small"),
                "V": st.column_config.NumberColumn("Vitórias", width="extra small", format="%d"),
                "D": st.column_config.NumberColumn("Derrotas", width="extra small", format="%d"),
                "E": st.column_config.NumberColumn("Empates", width="extra small", format="%d"),
                "PCT": st.column_config.TextColumn("PCT", width="small"),
            }
        )
    st.markdown("<br>", unsafe_allow_html=True)

def display_scoreboard(df_pfr, current_week_espn=None):
    if df_pfr.empty:
        st.info("Não há dados de jogos finalizados para esta temporada na base histórica.")
        return
    if current_week_espn:
        st.header(f"🗓️ Semana Atual: :green[{current_week_espn}]")
        df_display = df_pfr[df_pfr['Week'] == current_week_espn].copy()
        if df_display.empty:
             max_week = df_pfr['Week'].max()
             st.subheader(f"⚠️ Sem jogos finalizados na Semana {current_week_espn}. Mostrando a última semana jogada: **{max_week}**.")
             df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    else:
        max_week = df_pfr['Week'].max()
        st.header(f"🗓️ Última Semana Jogada: :orange[{max_week}]")
        df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    games_list = df_display[['Week', 'Date_Full', 'Winner_Abbr', 'Loser_Abbr', 'Winner_Pts', 'Loser_Pts']].to_dict('records')
    if not games_list:
        st.info(f"Nenhum jogo encontrado para exibição nesta semana.")
        return
    num_cols = 3
    for i in range(0, len(games_list), num_cols):
        cols = st.columns(num_cols)
        for j in range(num_cols):
            game_index = i + j
            if game_index < len(games_list):
                game = games_list[game_index]
                winner_abbr = game['Winner_Abbr']
                loser_abbr = game['Loser_Abbr']
                winner_pts = int(game['Winner_Pts'])
                loser_pts = int(game['Loser_Pts'])
                game_html = f"""
                <div class="pfr-root">
                  <div class="scoreboard-card pfr-card">
                    <div class="game-date">
                        🗓️ {game['Date_Full']}
                    </div>
                    <div class="game-layout">
                        <div class="team-info">
                            <img src="{get_logo_url(winner_abbr)}" alt="{winner_abbr} Logo">
                            <strong>{winner_abbr}</strong>
                        </div>
                        <div class="score-container">
                            <span class="score-winner">{winner_pts}</span>
                            <span class="vs-text">VS</span>
                            <span class="score-loser">{loser_pts}</span>
                        </div>
                        <div class="team-info">
                            <img src="{get_logo_url(loser_abbr)}" alt="{loser_abbr} Logo">
                            <strong>{loser_abbr}</strong>
                        </div>
                    </div>
                    <div class="status-final">
                        <span style="color: #198754;">• FINALIZADO</span>
                    </div>
                  </div>
                </div>
                """
                with cols[j]:
                    st.markdown(game_html, unsafe_allow_html=True)

inject_custom_css()

historical_data = load_historical_events_from_nflverse(CURRENT_PFR_YEAR)
current_week_espn, live_events = load_live_events_from_espn()

col_left, col_center, col_right = st.columns([0.1, 4, 0.1])

with col_center:
    st.title(f"🏈 :blue[Dashboard Histórico NFL] {CURRENT_PFR_YEAR}")
    st.markdown(f"Resultado e Classificação da Temporada Regular **{CURRENT_PFR_YEAR}**.")
    st.markdown("---")
    if historical_data.empty:
        st.error("O processamento não retornou dados. Verifique as mensagens de erro/aviso acima.")
    else:
        display_scoreboard(historical_data, current_week_espn)
        st.divider()
        standings_data = calculate_standings(historical_data)
        st.header("🏆 Classificação da Temporada")
        st.info("Veja a situação atual das conferências por divisão. As cores do título (azul/vermelho) ajudam a identificar as conferências.")
        col_afc, col_nfc = st.columns([1, 1])
        with col_afc:
            display_standings(standings_data, 'AFC')
        with col_nfc:
            display_standings(standings_data, 'NFC')
        st.header("Explorar Outras Semanas")
        st.markdown("Visualize os resultados detalhados de qualquer semana já jogada.")
        st.text("")
        all_weeks = sorted(historical_data['Week'].unique())
        default_index = len(all_weeks) - 1
        if current_week_espn is not None and current_week_espn in all_weeks:
            default_index = all_weeks.index(current_week_espn)
        elif all_weeks:
             default_index = all_weeks.index(all_weeks[-1])
        selected_week = st.selectbox(
            'Selecione a Semana para Visualizar os Resultados:',
            options=all_weeks,
            index=default_index,
            key='week_selector'
        )
        if selected_week is not None:
            df_selected_week = historical_data[historical_data['Week'] == selected_week].copy()
            if not df_selected_week.empty:
                st.subheader(f"Resultados Detalhados da Semana :red[{selected_week}] ({CURRENT_PFR_YEAR})")
                df_selected_week['Placar Final'] = df_selected_week.apply(
                    lambda row: f"**{row['Winner_PFR']}** ({int(row['Winner_Pts'])}) venceu {row['Loser_PFR']} ({int(row['Loser_Pts'])})",
                    axis=1
                )
                df_final_view = df_selected_week[[
                    'Date_Full',
                    'Placar Final',
                ]].rename(columns={'Date_Full': 'Data'})
                st.dataframe(
                    df_final_view,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Data": "Data do Jogo",
                        "Placar Final": "Resultado",
                    }
                )
            else:
                st.info(f"Nenhum jogo finalizado encontrado na base histórica para a Semana {selected_week}.")
