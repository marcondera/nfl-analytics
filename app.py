# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests
from io import StringIO
import re
from datetime import datetime, timezone
import time
from requests.exceptions import ConnectionError, Timeout, HTTPError 

# Importa as configurações globais
from config import CONFIG

# --- CONFIGURAÇÃO GLOBAL ---
PFR_YEAR = CONFIG['GERAL']['CURRENT_PFR_YEAR']
API_URL_SCOREBOARD_BACKUP = CONFIG['GERAL']['API_URL_SCOREBOARD']
API_URL_LIVE_PARTNERS = CONFIG['GERAL'].get('API_URL_LIVE_PARTNERS', 'https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025')
NFLVERSE_URL = CONFIG['GERAL']['NFLVERSE_GAMES_URL']
LOGO_MAP = CONFIG['MAPS']['LOGO_MAP']
NAME_MAP = CONFIG['MAPS']['PFR_NAME_MAP_REVERSE']
ABBR_CORR = CONFIG['MAPS']['ABBR_CORRECTIONS']
CONF_DIV_MAP = CONFIG['STANDINGS']['TEAM_CONFERENCE_DIVISION_MAP']
CACHE_TTL = CONFIG['GERAL']['CACHE_EXPIRY_SECONDS']

# --- FUNÇÕES DE UTILIDADE (MANTIDAS DO MARCONDES.PY) ---

def get_logo_url(abbreviation):
    """Retorna o URL do logo de um time."""
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_team_display_name(abbr):
    """Retorna o nome completo do time para exibição."""
    return NAME_MAP.get(abbr, abbr)

def standardize_abbr(abbr):
    """Padroniza e corrige abreviações."""
    if pd.isna(abbr) or not abbr: return None
    abbr_str = str(abbr).upper()
    if abbr_str in ABBR_CORR: abbr_str = ABBR_CORR[abbr_str]
    if abbr_str not in CONF_DIV_MAP: return None
    return abbr_str

def get_highlight_search_url(winner_abbr, loser_abbr, year):
    """Gera um URL de pesquisa do YouTube."""
    winner_name = get_team_display_name(winner_abbr)
    loser_name = get_team_display_name(loser_abbr)
    query = f"NFL Brasil {year} melhores momentos {winner_name} vs {loser_name}"
    return f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

def calculate_result(row):
    """Calcula o resultado final de um jogo."""
    # (A lógica de calculate_result é a mesma do marcondes.py)
    # ... (O código completo desta função seria copiado aqui) ...
    home_score = row['home_score']
    away_score = row['away_score']
    home_team = standardize_abbr(row['home_team'])
    away_team = standardize_abbr(row['away_team'])

    if home_team is None or away_team is None:
        return pd.Series([None] * 10)

    if home_score > away_score:
        winner_abbr, winner_pts = home_team, home_score
        loser_abbr, loser_pts = away_team, away_score
        is_tie = False
    elif away_score > home_score:
        winner_abbr, winner_pts = away_team, away_score
        loser_abbr, loser_pts = home_team, home_score
        is_tie = False
    else:
        winner_abbr, winner_pts = home_team, home_score
        loser_abbr, loser_pts = away_team, away_score
        is_tie = True

    winner_name = get_team_display_name(winner_abbr)
    loser_name = get_team_display_name(loser_abbr)

    if is_tie:
        result_str = f"**{winner_name}** ({int(winner_pts)}) empatou com {loser_name} ({int(loser_pts)})"
    else:
        result_str = f"**{winner_name}** ({int(winner_pts)}) venceu {loser_name} ({int(loser_pts)})"

    return pd.Series([
        row['week'], row['gameday'], winner_name, winner_abbr, winner_pts, 
        loser_name, loser_abbr, loser_pts, is_tie, result_str
    ])

def calculate_standings(df_games):
    """Calcula a classificação atualizada."""
    # (A lógica de calculate_standings é a mesma do marcondes.py)
    # ... (O código completo desta função seria copiado aqui) ...
    standings = {abbr: {'W': 0, 'L': 0, 'T': 0} for abbr in CONF_DIV_MAP.keys()}

    for _, game in df_games.iterrows():
        winner_abbr = game['Winner_Abbr']
        loser_abbr = game['Loser_Abbr']
        is_tie = game['Is_Tie']

        if winner_abbr in standings and loser_abbr in standings:
            if is_tie:
                standings[winner_abbr]['T'] += 1
                standings[loser_abbr]['T'] += 1
            else:
                standings[winner_abbr]['W'] += 1
                standings[loser_abbr]['L'] += 1

    df_standings = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Abbr'})
    df_standings['Conf'] = df_standings['Abbr'].apply(lambda x: CONF_DIV_MAP.get(x, {}).get('conf', 'N/A'))
    df_standings['Div'] = df_standings['Abbr'].apply(lambda x: CONF_DIV_MAP.get(x, {}).get('div', 'N/A'))
    
    df_standings = df_standings[df_standings['Conf'] != 'N/A'].copy()
    df_standings['GP'] = df_standings['W'] + df_standings['L'] + df_standings['T']
    df_standings['PCT'] = (df_standings['W'] + 0.5 * df_standings['T']) / df_standings['GP'].replace(0, 1)
    df_standings.loc[df_standings['GP'] == 0, 'PCT'] = 0.000
    df_standings['PCT_Str'] = df_standings['PCT'].map('{:.3f}'.format)
    df_standings['Time'] = df_standings['Abbr'].apply(get_team_display_name)

    standings_output = {'AFC': {}, 'NFC': {}}
    for conf in ['AFC', 'NFC']:
        conf_df = df_standings[df_standings['Conf'] == conf].copy()
        divisions = sorted(conf_df['Div'].unique())
        for div in divisions:
            div_df = conf_df[conf_df['Div'] == div].copy()
            div_df = div_df.sort_values(by=['PCT', 'W', 'T'], ascending=[False, False, False])
            standings_output[conf][div] = div_df[['Time', 'Abbr', 'W', 'L', 'T', 'PCT_Str']].to_dict('records')

    return standings_output

def format_date_br(datestring):
    """Formata datas para o formato brasileiro."""
    # (A lógica de format_date_br é a mesma do marcondes.py)
    # ... (O código completo desta função seria copiado aqui) ...
    if not datestring: return ""
    month_names = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
                   7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    try:
        date_obj = pd.to_datetime(datestring).replace(tzinfo=timezone.utc)
        day = date_obj.day
        month = month_names[date_obj.month]
        year = date_obj.year
        if date_obj.hour == 0 and date_obj.minute == 0:
            return f"{day:02d} de {month} de {year}" 
        else:
            time_str = date_obj.strftime('%H:%Mh')
            return f"{day:02d} de {month}, {year} - {time_str} UTC" 
    except:
        try:
            date_obj = datetime.strptime(str(datestring).split(' ')[0], '%Y-%m-%d')
            day = date_obj.day
            month = month_names[date_obj.month]
            year = date_obj.year
            return f"{day:02d} de {month} de {year}"
        except:
            return str(datestring)


# --- FUNÇÕES DE CARREGAMENTO DE DADOS COM CACHE STREAMLIT ---

# Streamlit lida com o cache e a expiração (TTL)
@st.cache_data(ttl=CACHE_TTL)
def load_historical_events_from_nflverse(year):
    """Carrega dados históricos de jogos do nflverse com cache."""
    # (O código desta função é o mesmo, mas a lógica de cache manual foi removida)
    try:
        response = requests.get(NFLVERSE_URL, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(StringIO(response.text))
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        
        df_year['home_score'] = pd.to_numeric(df_year['home_score'], errors='coerce').fillna(0)
        df_year['away_score'] = pd.to_numeric(df_year['away_score'], errors='coerce').fillna(0)
        
        # Lógica de cálculo de semanas e processamento de jogos...
        df_played = df_year[(df_year['home_score'] > 0) | (df_year['away_score'] > 0)].copy()

        if df_played.empty:
            df_future = df_year[~((df_year['home_score'] > 0) | (df_year['away_score'] > 0))].copy()
            df_future['home_team_name'] = df_future['home_team'].apply(get_team_display_name)
            df_future['away_team_name'] = df_future['away_team'].apply(get_team_display_name)
            df_future = df_future.rename(columns={'gameday': 'Date_Full', 'week': 'Week'})
            df_future['start_time'] = pd.to_datetime(df_future['Date_Full'] + ' ' + df_future['gametime'], errors='coerce')
            
            info_message = "Nenhum jogo finalizado encontrado no NFLverse."
            return pd.DataFrame(), df_future, info_message, None, None

        df_results = df_played.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts', 'Is_Tie', 'Result_Display_Str']
        df_results = df_results.dropna(subset=['Winner_Abbr', 'Week'])
        df_results['Week'] = pd.to_numeric(df_results['Week'], errors='coerce').astype('Int64')

        max_week_played = df_results['Week'].max()
        
        games_per_week = df_year[(df_year['home_score'] > 0) | (df_year['away_score'] > 0)].groupby('week').size()
        total_games_per_week = df_year[df_year['week'].isin(games_per_week.index)].groupby('week').size()
        fully_played_weeks = total_games_per_week[total_games_per_week == games_per_week].index
        last_fully_played_week = fully_played_weeks.max() if not fully_played_weeks.empty else None

        df_future = df_year[~((df_year['home_score'] > 0) | (df_year['away_score'] > 0))].copy()
        
        df_future['home_team_name'] = df_future['home_team'].apply(get_team_display_name)
        df_future['away_team_name'] = df_future['away_team'].apply(get_team_display_name)
        df_future = df_future.rename(columns={'gameday': 'Date_Full', 'week': 'Week'})

        df_future['start_time'] = pd.to_datetime(df_future['Date_Full'] + ' ' + df_future['gametime'], errors='coerce')

        info_message = f"Dados históricos até a Semana {max_week_played} carregados."
        return df_results, df_future, info_message, max_week_played, last_fully_played_week

    except requests.exceptions.RequestException as e:
        return pd.DataFrame(), pd.DataFrame(), f"Erro ao carregar NFLverse (HTTP/Rede): {e}", None, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"Erro durante processamento (Pandas/JSON): {e}", None, None

@st.cache_data(ttl=600) # Cache mais curto para a semana atual (10 minutos)
def load_current_week_espn(url):
    """Tenta carregar a semana atual da ESPN."""
    # (O código desta função é o mesmo do marcondes.py)
    try:
        response = requests.get(url, timeout=10) 
        response.raise_for_status()
        data = response.json()
        
        week_name = data.get('week', {}).get('text')
        if week_name:
            current_week = int(re.search(r'\d+', week_name).group()) if re.search(r'\d+', week_name) else None
            return current_week
        
        sport_data = data.get('sports', [{}])[0]
        nfl_league = next((l for l in sport_data.get('leagues', []) if l.get('abbreviation') == 'NFL'), None)
        if nfl_league:
            for event in nfl_league.get('events', []):
                links = event.get('links', [])
                for link in links:
                    href = link.get('href', '')
                    match = re.search(r'week=(\d+)', href)
                    if match:
                        return int(match.group(1))

        return None
    except Exception:
        return None

# Cache mais curto para jogos ao vivo (30 segundos)
@st.cache_data(ttl=30)
def load_live_games_api(url, current_week, api_name="API ESPN Partners"):
    """Carrega jogos ao vivo, com tratamento de erros."""
    # (O código desta função é o mesmo do marcondes.py)
    live_games = []
    live_teams_pair = set()
    error_message = ""

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # ... (A lógica de parsing do JSON da ESPN é copiada aqui) ...
        sport_data = data.get('sports', [{}])[0]
        nfl_league = next((l for l in sport_data.get('leagues', []) if l.get('abbreviation') == 'NFL'), None)

        if not nfl_league:
            error_message = f"Estrutura da resposta da {api_name} inválida ou sem eventos NFL."
            if 'error' in data:
                 error_message = f"Erro da API {api_name}: {data.get('error', 'Erro desconhecido na resposta JSON')}"
            return live_games, live_teams_pair, error_message

        for event in nfl_league.get('events', []):
            competition = event.get('competitions', [None])[0] 
            
            if competition is None: continue
            
            status = competition.get('status', {})
            status_state = status.get('type', {}).get('state')
            status_detail = status.get('type', {}).get('detail')

            if status_state in ['in', 'post']: 
                competitors = competition.get('competitors', [])
                
                home_team, away_team = None, None
                home_score, away_score = 0, 0
                
                for comp in competitors:
                    if comp.get('homeAway') == 'home':
                        home_team_abbr = standardize_abbr(comp.get('team', {}).get('abbreviation'))
                        if home_team_abbr:
                             home_team = home_team_abbr
                             home_score = comp.get('score', 0)
                    elif comp.get('homeAway') == 'away':
                        away_team_abbr = standardize_abbr(comp.get('team', {}).get('abbreviation'))
                        if away_team_abbr:
                             away_team = away_team_abbr
                             away_score = comp.get('score', 0)
                
                home_score = int(home_score)
                away_score = int(away_score)
                
                if home_team and away_team:
                    game_data = {
                        'home_team': home_team, 'away_team': away_team, 'home_score': home_score,
                        'away_score': away_score, 'Date_Full': event.get('date'), 'Week': current_week,
                        'status_state': status_state, 'status_detail': status_detail,
                        'is_halftime': 'Halftime' in status_detail or 'Intervalo' in status_detail
                    }
                    live_games.append(game_data)
                    
                    if status_state == 'in':
                        live_teams_pair.add((home_team, away_team))
                    
        return live_games, live_teams_pair, error_message

    except ConnectionError as e:
        error_message = f"Erro de CONEXÃO (HTTP/Rede) à {api_name}. Detalhes: ConnectionError - {e}"
    except Timeout:
        error_message = f"Erro de TIMEOUT à {api_name}. Detalhes: A requisição HTTP demorou mais que 10 segundos."
    except HTTPError as e:
        error_message = f"Erro HTTP {e.response.status_code} à {api_name}. Detalhes: O servidor recusou a requisição."
    except Exception as e:
        error_message = f"Erro inesperado no carregamento da {api_name}. Detalhes: {type(e).__name__} - {e}"

    return live_games, live_teams_pair, error_message


# --- FUNÇÃO DE RENDERIZAÇÃO DE CARD HTML (Para replicar o estilo do game_card.html) ---

def render_game_card_html(game, is_live=False):
    """Gera o HTML do card de jogo para injeção no Streamlit."""
    
    # Adiciona classe para live game se necessário
    card_class = "scoreboard-card pfr-card"
    status_text = ""
    
    if is_live:
        card_class += " live-game-card"
        if game.get('is_halftime'):
             status_text = '<span class="status-live" style="color:#ffc107;">• INTERVALO</span>'
        else:
             status_text = f'<span class="status-live" style="color:#dc3545;">• AO VIVO ({game.get("status_detail", "")})</span>'
        home_abbr = standardize_abbr(game['home_team'])
        away_abbr = standardize_abbr(game['away_team'])
        winner_abbr = home_abbr if game['home_score'] > game['away_score'] else away_abbr
        loser_abbr = away_abbr if game['home_score'] > game['away_score'] else home_abbr
        winner_pts = max(game['home_score'], game['away_score'])
        loser_pts = min
