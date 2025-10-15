import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime
import json
import math
import re
from io import StringIO
import time

# --- CONFIGURAÇÃO ---

# CORRIGIDO: Agora usando nflverse como fonte principal para dados históricos.
CURRENT_PFR_YEAR = 2023 

st.set_page_config(page_title=f"🏈 NFL Dashboard Histórico {CURRENT_PFR_YEAR}", layout="wide", page_icon="🏈")

# Endpoints
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
# Nova URL de dados históricos - fonte mais robusta e estável
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/refs/heads/master/data/games.csv"

# Mapa de Logos (nflverse usa as abreviações padrão que já mapeamos)
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "pit": "pit", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

# Mapeamento de nomes completos/curtos (usado para simular os nomes PFR que o código espera)
PFR_ABBR_MAP = {
    '49ers': 'SF', 'Bills': 'BUF', 'Falcons': 'ATL', 'Ravens': 'BAL', 'Panthers': 'CAR', 'Bengals': 'CIN',
    'Bears': 'CHI', 'Browns': 'CLE', 'Cowboys': 'DAL', 'Broncos': 'DEN', 'Lions': 'DET', 'Packers': 'GB',
    'Texans': 'HOU', 'Colts': 'IND', 'Jaguars': 'JAX', 'Chiefs': 'KC', 'Chargers': 'LAC', 'Rams': 'LAR',
    'Raiders': 'LV', 'Dolphins': 'MIA', 'Vikings': 'MIN', 'Patriots': 'NE', 'Saints': 'NO', 'Giants': 'NYG',
    'Jets': 'NYJ', 'Eagles': 'PHI', 'Steelers': 'PIT', 'Seahawks': 'SEA', 'Buccaneers': 'TB', 'Titans': 'TEN',
    'Cardinals': 'ARI', 'Commanders': 'WSH',
    # Nomes mais longos/inconsistentes
    'San Francisco': 'SF', 'Buffalo': 'BUF', 'Atlanta': 'ATL', 'Baltimore': 'BAL', 'Carolina': 'CAR', 'Cincinnati': 'CIN',
    'Chicago': 'CHI', 'Cleveland': 'CLE', 'Dallas': 'DAL', 'Denver': 'DEN', 'Detroit': 'DET', 'Green Bay': 'GB',
    'Houston': 'HOU', 'Indianapolis': 'IND', 'Jacksonville': 'JAX', 'Kansas City': 'KC', 'Los Angeles Chargers': 'LAC', 'Los Angeles Rams': 'LAR',
    'Las Vegas': 'LV', 'Miami': 'MIA', 'Minnesota': 'MIN', 'New England': 'NE', 'New Orleans': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia': 'PHI', 'Pittsburgh': 'PIT', 'Seattle': 'SEA', 'Tampa Bay': 'TB', 'Tennessee': 'TEN',
    'Arizona': 'ARI', 'Washington': 'WSH'
}

def get_logo_url(abbreviation):
    """Gera URL do logo baseada na abreviação."""
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse(year):
    """
    Carrega o histórico de eventos (jogos) do nflverse (via CSV).
    Usa uma fonte de dados mais estável para evitar bloqueios de scraping.
    """
    st.info(f"Carregando dados históricos do NFLverse para a temporada: **{year}** a partir de `{NFLVERSE_GAMES_URL}`. Aguarde...")

    try:
        # Lê o CSV diretamente da URL
        df = pd.read_csv(NFLVERSE_GAMES_URL)
        
        # Filtra pelo ano (season) e apenas jogos da temporada regular ('REG') que já terminaram
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        
        if df_year.empty:
            st.warning(f"Nenhum jogo encontrado no NFLverse para a temporada {year}.")
            return pd.DataFrame()

        # Cria as colunas de Vencedor/Perdedor e Placar, mantendo a estrutura esperada pelo Dashboard
        
        # Cria um mapeamento simples de ABBR para um nome completo simulado para manter a estrutura de exibição
        # do PFR original (ex: '49ers' em vez de 'SF' para o nome completo)
        ABBR_TO_NAME = {v: k for k, v in PFR_ABBR_MAP.items() if v == k.split()[-1] or v == k}
            
        def calculate_result(row):
            winner_abbr, loser_abbr, winner_pts, loser_pts = None, None, 0, 0
            
            # Garante que scores são inteiros para comparação
            home_score = int(row['home_score']) if pd.notna(row['home_score']) else 0
            away_score = int(row['away_score']) if pd.notna(row['away_score']) else 0
            
            if home_score > away_score:
                winner_abbr, winner_pts = row['home_team'], home_score
                loser_abbr, loser_pts = row['away_team'], away_score
            elif away_score > home_score:
                winner_abbr, winner_pts = row['away_team'], away_score
                loser_abbr, loser_pts = row['home_team'], home_score
            else: # Empate (Tie) ou 0-0
                # Para simplificar a exibição (o dashboard não lida bem com empates), 
                # e para jogos não jogados (0-0), tratamos o time da casa como 'vencedor'.
                winner_abbr, winner_pts = row['home_team'], home_score
                loser_abbr, loser_pts = row['away_team'], away_score
            
            # Simula os nomes completos (PFR_PFR)
            winner_name = ABBR_TO_NAME.get(winner_abbr, winner_abbr)
            loser_name = ABBR_TO_NAME.get(loser_abbr, loser_abbr)

            return pd.Series([
                row['week'], 
                f"{row['gameday']} {row['season']}", # Date_Full
                winner_name,  # Winner_PFR (Nome completo simulado)
                winner_abbr,  # Winner_Abbr
                winner_pts, 
                loser_name,   # Loser_PFR (Nome completo simulado)
                loser_abbr,   # Loser_Abbr
                loser_pts,
                'N/A' # Boxscore placeholder
            ])

        # Aplica a função para criar as novas colunas no formato do dashboard
        df_results = df_year.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts', 'Boxscore']
        
        df_results['Week'] = pd.to_numeric(df_results['Week'], errors='coerce').astype('Int64')
        df_results = df_results.dropna(subset=['Week'])
        
        st.success(f"Dados históricos da Semana {df_results['Week'].max()} carregados com sucesso do NFLverse para {year}.")
        return df_results
        
    except requests.exceptions.RequestException as he:
        st.error(f"Erro de rede ao carregar NFLverse: {he}. Verifique a conectividade ou a URL de dados.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro carregando e processando eventos do NFLverse: {e}")
        return pd.DataFrame()


# --- CARREGAMENTO DE DADOS (NFLVERSE - SUBSTITUI PFR) ---
# Altera a chamada da função para a nova fonte de dados
historical_data = load_historical_events_from_nflverse(CURRENT_PFR_YEAR)


# --- CARREGAMENTO DE DADOS (ESPN) ---
@st.cache_data(ttl=600)
def load_live_events_from_espn():
    """Carrega o scoreboard atual da ESPN para verificar a semana ativa."""
    try:
        response = requests.get(API_URL_SCOREBOARD)
        response.raise_for_status()
        data = response.json()
        
        # Extrai o nome da semana ativa (ex: 'Week 17')
        week_name = data.get('week', {}).get('text', 'Semana Atual Não Definida')
        current_week = int(re.search(r'\d+', week_name).group()) if re.search(r'\d+', week_name) else None
        
        return current_week, data.get('events', [])
    except Exception as e:
        st.error(f"Erro carregando dados em tempo real da ESPN: {e}")
        return None, []

# --- FUNÇÃO DE BUSCA E VISUALIZAÇÃO ---

def display_scoreboard(df_pfr, current_week_espn=None):
    """Exibe o placar formatado com base nos dados históricos do PFR (agora nflverse)."""

    if df_pfr.empty:
        st.warning("Não há dados históricos disponíveis para exibição.")
        return

    # Usar a semana mais alta disponível nos dados PFR se o ESPN não retornar
    if current_week_espn:
        st.subheader(f"🏈 Calendário da Temporada {CURRENT_PFR_YEAR} (Semana {current_week_espn} - ESPN)")
        df_display = df_pfr[df_pfr['Week'] == current_week_espn].copy()
    else:
        max_week = df_pfr['Week'].max()
        st.subheader(f"🏈 Calendário da Temporada {CURRENT_PFR_YEAR} (Semana {max_week} - NFLverse)")
        df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    
    # Prepara o DataFrame para exibição
    # Certifica-se de que as colunas Winner_Pts e Loser_Pts são numéricas antes de formatar
    df_display['Winner_Pts'] = pd.to_numeric(df_display['Winner_Pts'], errors='coerce').fillna(0).astype(int)
    df_display['Loser_Pts'] = pd.to_numeric(df_display['Loser_Pts'], errors='coerce').fillna(0).astype(int)

    df_display['Vencedor'] = df_display.apply(
        lambda row: f"{row['Winner_PFR']} ({row['Winner_Pts']})", axis=1
    )
    df_display['Perdedor'] = df_display.apply(
        lambda row: f"{row['Loser_PFR']} ({row['Loser_Pts']})", axis=1
    )
    df_display['Placar'] = df_display['Vencedor'] + ' vs ' + df_display['Perdedor']
    
    # Colunas para visualização simplificada
    games_list = df_display[['Week', 'Date_Full', 'Placar', 'Winner_Abbr', 'Loser_Abbr', 'Winner_Pts', 'Loser_Pts']].to_dict('records')

    if not games_list:
        st.info(f"Nenhum jogo encontrado para esta semana na base de dados histórica.")
        return

    # Layout de cards para melhor visualização
    # Adiciona max-width para melhor responsividade
    st.markdown('<style>div.css-1e69z9b {max-width: 1200px !important; margin: auto;}</style>', unsafe_allow_html=True)
    
    cols = st.columns(min(len(games_list), 3)) 
    
    for i, game in enumerate(games_list):
        with cols[i % 3]:
            winner_abbr = game['Winner_Abbr']
            loser_abbr = game['Loser_Abbr']
            winner_pts = game['Winner_Pts']
            loser_pts = game['Loser_Pts']

            # Define o status do jogo. Para nflverse, jogos com scores > 0 já estão finalizados.
            status_text = "FINALIZADO"
            if winner_pts == 0 and loser_pts == 0:
                status_text = "AGENDADO" # Usado se o nflverse listar jogos futuros

            # Card com estilização básica
            st.markdown(
                f"""
                <div style="
                    border: 2px solid #282c34; 
                    border-radius: 12px; 
                    padding: 15px; 
                    margin-bottom: 15px;
                    background-color: #0e1117;
                    box-shadow: 4px 4px 10px rgba(0,0,0,0.5);
                    color: #fff;
                    text-align: center;
                ">
                    <p style="font-size: 1.1em; font-weight: bold; margin-bottom: 5px; color: #4CAF50;">
                        SEMANA {game['Week']}
                    </p>
                    <p style="font-size: 0.9em; color: #aaa; margin-bottom: 15px;">
                        {game['Date_Full']}
                    </p>
                    <div style="display: flex; justify-content: space-around; align-items: center;">
                        <div style="text-align: center; flex: 1;">
                            <img src="{get_logo_url(winner_abbr)}" width="48" style="border-radius: 5px;">
                            <p style="font-weight: bold; margin-top: 5px; color: #fff;">{winner_abbr}</p>
                            <span style="font-size: 1.5em; font-weight: 900; color: #4CAF50;">{winner_pts}</span>
                        </div>
                        <span style="font-weight: 900; font-size: 1.2em; color: #aaa; margin: 0 10px;">VS</span>
                        <div style="text-align: center; flex: 1;">
                            <img src="{get_logo_url(loser_abbr)}" width="48" style="border-radius: 5px;">
                            <p style="font-weight: bold; margin-top: 5px; color: #fff;">{loser_abbr}</p>
                            <span style="font-size: 1.5em; font-weight: 900; color: #FF4B4B;">{loser_pts}</span>
                        </div>
                    </div>
                     <p style="font-size: 0.8em; font-weight: 600; margin-top: 15px; color: {
                        '#4CAF50' if status_text == 'FINALIZADO' else '#FFD700'
                    }">
                        {status_text}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

# --- APLICAÇÃO PRINCIPAL ---

st.title(f"🏈 Dashboard Histórico NFL {CURRENT_PFR_YEAR}")
st.markdown(f"**Fonte de dados:** ESPN (Semana Atual) e **NFLverse** (Resultados Históricos para {CURRENT_PFR_YEAR})")

# 1. Carrega dados da ESPN para saber a semana atual
current_week_espn, live_events = load_live_events_from_espn()

if historical_data.empty:
    st.error("Não foi possível carregar o calendário histórico do NFLverse. Verifique se o ano está correto ou se a URL de dados mudou.")
else:
    # 2. Exibe o placar
    display_scoreboard(historical_data, current_week_espn)

# 3. Adiciona um filtro de semana caso o usuário queira ver outras semanas
if not historical_data.empty:
    all_weeks = sorted(historical_data['Week'].unique())
    
    st.markdown("---")
    st.header("Explorar Outras Semanas")

    # Garante que o índice selecionado é válido
    default_index = 0
    if current_week_espn in all_weeks:
        default_index = all_weeks.index(current_week_espn)
    elif all_weeks:
        # Seleciona a última semana se a atual não for encontrada
        default_index = all_weeks.index(all_weeks[-1]) 

    selected_week = st.selectbox(
        'Selecione a Semana para Visualizar:',
        options=all_weeks,
        index=default_index
    )

    if selected_week is not None:
        df_selected_week = historical_data[historical_data['Week'] == selected_week].copy()
        
        if not df_selected_week.empty:
            st.subheader(f"Resultados da Semana {selected_week} ({CURRENT_PFR_YEAR})")
            
            # Prepara a tabela de visualização
            df_selected_week['Placar Final'] = df_selected_week.apply(
                lambda row: f"**{row['Winner_PFR']}** {int(row['Winner_Pts'])} - {int(row['Loser_Pts'])} **{row['Loser_PFR']}**", 
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
            )
        else:
            st.info(f"Nenhum jogo encontrado na base de dados histórica para a Semana {selected_week} de {CURRENT_PFR_YEAR}.")
