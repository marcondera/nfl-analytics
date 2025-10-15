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

# --- CONFIGURAÇÃO E ESTILO GLOBAL ---

CURRENT_PFR_YEAR = 2025 

# Configurações iniciais do Streamlit (título, layout)
st.set_page_config(page_title=f"🏈 NFL Dashboard Histórico {CURRENT_PFR_YEAR}", layout="wide", page_icon="🏈")

# NOVO: Injeção de CSS para o tema escuro/foco NFL (Garante que o design seja aplicado corretamente)
st.markdown("""
<style>
    /* Fundo principal e containers */
    .stApp {
        background-color: #0c0c0e; /* NFL Dark Black */
        color: #F0F2F6;
    }
    
    /* Cabeçalhos e texto */
    h1, h2, h3, h4, h5, h6 {
        color: #F0F2F6 !important;
    }

    /* Estilo do DataFrame (tabelas de Classificação) */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #333;
    }
    
    /* Cor de fundo do cabeçalho da tabela */
    .stDataFrame table th {
        background-color: #1E2129 !important; 
        color: #8D99AE !important;
    }
    
    /* Cor das linhas do corpo da tabela */
    .stDataFrame table tbody tr {
        background-color: #1E2129;
    }
    
    /* Hover nas linhas */
    .stDataFrame table tbody tr:hover {
        background-color: #282c34 !important;
    }

    /* Linha divisória */
    hr {
        border-top: 1px solid #333;
    }

    /* Elementos de informação/sucesso */
    div[data-testid="stAlert"] {
        border-radius: 8px;
        background-color: #1E2129;
    }
</style>
""", unsafe_allow_html=True)


# Endpoints
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# Mapa de Logos (nflverse usa as abreviações padrão que já mapeamos)
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "pit": "pit", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

# Mapeamento de nomes completos/curtos para exibição
PFR_ABBR_MAP = {
    '49ers': 'SF', 'Bills': 'BUF', 'Falcons': 'ATL', 'Ravens': 'BAL', 'Panthers': 'CAR', 'Bengals': 'CIN',
    'Bears': 'CHI', 'Browns': 'CLE', 'Cowboys': 'DAL', 'Broncos': 'DEN', 'Lions': 'DET', 'Packers': 'GB',
    'Texans': 'HOU', 'Colts': 'IND', 'Jaguars': 'JAX', 'Chiefs': 'KC', 'Chargers': 'LAC', 'Rams': 'LAR',
    'Raiders': 'LV', 'Dolphins': 'MIA', 'Vikings': 'MIN', 'Patriots': 'NE', 'Saints': 'NO', 'Giants': 'NYG',
    'Jets': 'NYJ', 'Eagles': 'PHI', 'Steelers': 'PIT', 'Seahawks': 'SEA', 'Buccaneers': 'TB', 'Titans': 'TEN',
    'Cardinals': 'ARI', 'Commanders': 'WSH'
}

PFR_NAME_MAP_REVERSE = {
    v: k for k, v in PFR_ABBR_MAP.items() 
    if len(k.split()) == 1 or v == k.split()[-1]
}

# Mapeamento de Conferência e Divisão (2020-presente)
TEAM_CONFERENCE_DIVISION_MAP = {
    'BUF': {'conf': 'AFC', 'div': 'East'}, 'MIA': {'conf': 'AFC', 'div': 'East'}, 
    'NE': {'conf': 'AFC', 'div': 'East'}, 'NYJ': {'conf': 'AFC', 'div': 'East'},
    
    'BAL': {'conf': 'AFC', 'div': 'North'}, 'CIN': {'conf': 'AFC', 'div': 'North'}, 
    'CLE': {'conf': 'AFC', 'div': 'North'}, 'PIT': {'conf': 'AFC', 'div': 'North'},
    
    'HOU': {'conf': 'AFC', 'div': 'South'}, 'IND': {'conf': 'AFC', 'div': 'South'}, 
    'JAX': {'conf': 'AFC', 'div': 'South'}, 'TEN': {'conf': 'AFC', 'div': 'South'},
    
    'DEN': {'conf': 'AFC', 'div': 'West'}, 'KC': {'conf': 'AFC', 'div': 'West'}, 
    'LV': {'conf': 'AFC', 'div': 'West'}, 'LAC': {'conf': 'AFC', 'div': 'West'},

    'DAL': {'conf': 'NFC', 'div': 'East'}, 'NYG': {'conf': 'NFC', 'div': 'East'}, 
    'PHI': {'conf': 'NFC', 'div': 'East'}, 'WSH': {'conf': 'NFC', 'div': 'East'},
    
    'CHI': {'conf': 'NFC', 'div': 'North'}, 'DET': {'conf': 'NFC', 'div': 'North'}, 
    'GB': {'conf': 'NFC', 'div': 'North'}, 'MIN': {'conf': 'NFC', 'div': 'North'},
    
    'ATL': {'conf': 'NFC', 'div': 'South'}, 'CAR': {'conf': 'NFC', 'div': 'South'}, 
    'NO': {'conf': 'NFC', 'div': 'South'}, 'TB': {'conf': 'NFC', 'div': 'South'},
    
    'ARI': {'conf': 'NFC', 'div': 'West'}, 'LAR': {'conf': 'NFC', 'div': 'West'}, 
    'SF': {'conf': 'NFC', 'div': 'West'}, 'SEA': {'conf': 'NFC', 'div': 'West'}
}

def get_logo_url(abbreviation):
    """Gera URL do logo baseada na abreviação."""
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_team_display_name(abbr):
    """Retorna o nome curto do time para exibição (ex: 'Bills' para 'BUF')."""
    return PFR_NAME_MAP_REVERSE.get(abbr, abbr)

@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse(year):
    """
    Carrega o histórico de eventos (jogos) do nflverse (via CSV).
    Inclui filtro para considerar apenas jogos jogados (scores > 0).
    """
    st.info(f"⏳ Carregando dados históricos do NFLverse para a temporada: **{year}** a partir de `{NFLVERSE_GAMES_URL}`. Aguarde...")

    try:
        # Lê o CSV diretamente da URL
        df = pd.read_csv(NFLVERSE_GAMES_URL)
        
        # Filtra pelo ano (season) e apenas jogos da temporada regular ('REG')
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        
        # FILTRO CRÍTICO: Garante que apenas jogos JOGADOS (com scores > 0) sejam considerados.
        df_year = df_year[(df_year['home_score'].fillna(0) > 0) | (df_year['away_score'].fillna(0) > 0)].copy()

        if df_year.empty:
            st.warning(f"Nenhum jogo jogado encontrado no NFLverse para a temporada {year}.")
            return pd.DataFrame()

        def calculate_result(row):
            # ... (logica de calculo de vencedor/perdedor, mantida igual)
            winner_abbr, loser_abbr, winner_pts, loser_pts = None, None, 0, 0
            
            home_score = int(row['home_score']) if pd.notna(row['home_score']) else 0
            away_score = int(row['away_score']) if pd.notna(row['away_score']) else 0
            
            if home_score > away_score:
                winner_abbr, winner_pts = row['home_team'], home_score
                loser_abbr, loser_pts = row['away_team'], away_score
            elif away_score > home_score:
                winner_abbr, winner_pts = row['away_team'], away_score
                loser_abbr, loser_pts = row['home_team'], away_score # Corrigido para ser o score do home_team
            else: # Empate (Tie)
                winner_abbr, winner_pts = row['home_team'], home_score
                loser_abbr, loser_pts = row['away_team'], away_score
            
            winner_name = get_team_display_name(winner_abbr)
            loser_name = get_team_display_name(loser_abbr)

            return pd.Series([
                row['week'], 
                f"{row['gameday']} {row['season']}", # Date_Full
                winner_name,  # Winner_PFR (Nome de exibição)
                winner_abbr,  # Winner_Abbr
                winner_pts, 
                loser_name,   # Loser_PFR (Nome de exibição)
                loser_abbr,   # Loser_Abbr
                loser_pts,
                'N/A' # Boxscore placeholder
            ])

        # Aplica a função para criar as novas colunas no formato do dashboard
        df_results = df_year.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts', 'Boxscore']
        
        df_results['Week'] = pd.to_numeric(df_results['Week'], errors='coerce').astype('Int64')
        df_results = df_results.dropna(subset=['Week'])
        
        st.success(f"✅ Dados históricos da Semana {df_results['Week'].max()} carregados com sucesso do NFLverse para {year}.")
        return df_results
        
    except Exception as e:
        st.error(f"❌ Erro carregando e processando eventos do NFLverse: {e}")
        return pd.DataFrame()


# --- FUNÇÕES DE CLASSIFICAÇÃO (STANDINGS) ---

def calculate_standings(df_games):
    """Calcula Vitórias, Derrotas, Empates e PCT para cada time."""
    # Inicializa todos os times para garantir que mesmo times sem jogos apareçam com 0-0-0
    standings = {abbr: {'W': 0, 'L': 0, 'T': 0} for abbr in TEAM_CONFERENCE_DIVISION_MAP.keys()}

    for _, game in df_games.iterrows():
        winner_abbr = game['Winner_Abbr']
        loser_abbr = game['Loser_Abbr']
        winner_pts = game['Winner_Pts']
        loser_pts = game['Loser_Pts']

        # O filtro já garante que scores > 0
        if winner_pts > loser_pts:
            standings[winner_abbr]['W'] += 1
            standings[loser_abbr]['L'] += 1
        elif winner_pts < loser_pts:
            # Caso raro: Aqui estamos assumindo que os dados já definiram Winner e Loser corretamente,
            # mas o código de cálculo de PCT precisa dos dados de V/D/E.
            standings[winner_abbr]['W'] += 1 # O "Winner_Abbr" da linha é o time com mais pontos.
            standings[loser_abbr]['L'] += 1 
        else: # Empate (Tie)
            standings[winner_abbr]['T'] += 1
            standings[loser_abbr]['T'] += 1

    df_standings = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Abbr'})
    
    # Adiciona Conferência e Divisão (Usando .get para ser mais defensivo)
    df_standings['Conf'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('conf', 'N/A'))
    df_standings['Div'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('div', 'N/A'))
    
    # Remove times que não estão no mapeamento (caso o nflverse tenha times antigos)
    df_standings = df_standings[df_standings['Conf'] != 'N/A'].copy()

    # Calcula PCT (Win Percentage)
    df_standings['GP'] = df_standings['W'] + df_standings['L'] + df_standings['T']
    df_standings['PCT'] = df_standings.apply(
        lambda row: (row['W'] + 0.5 * row['T']) / row['GP'] if row['GP'] > 0 else 0.000, axis=1
    )
    
    df_standings['PCT_Str'] = df_standings['PCT'].map('{:.3f}'.format)
    
    return df_standings

def display_standings(df_standings, conference_name):
    """Exibe a classificação por divisão para a Conferência especificada."""
    
    # NOVO DESIGN: Título da Conferência
    conf_color = "#FF4B4B" if conference_name == 'AFC' else "#4CAF50"
    st.markdown(f"<h3 style='color: {conf_color}; margin-bottom: 15px;'>{conference_name}</h3>", unsafe_allow_html=True)
    
    conf_df = df_standings[df_standings['Conf'] == conference_name].copy()
    
    # Itera sobre as divisões e exibe cada uma
    divisions = sorted(conf_df['Div'].unique())

    for div in divisions:
        # NOVO DESIGN: Título da Divisão
        st.markdown(f"<h5 style='color: #8D99AE; margin-bottom: 5px; margin-top: 15px;'>Divisão {div}</h5>", unsafe_allow_html=True)
        
        div_df = conf_df[conf_df['Div'] == div].copy()
        
        # Adiciona nome de exibição e classifica
        div_df['Time'] = div_df['Abbr'].apply(get_team_display_name)
        div_df = div_df.sort_values(by=['PCT', 'W', 'T'], ascending=[False, False, False])
        
        # Colunas finais de exibição
        display_cols = div_df[['Time', 'Abbr', 'W', 'L', 'T', 'PCT_Str']]
        
        st.dataframe(
            display_cols.rename(columns={'Abbr': 'Abbr.', 'W': 'V', 'L': 'D', 'T': 'E', 'PCT_Str': 'PCT'}),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Time": st.column_config.TextColumn("Time", help="Nome do Time", width="large"),
                "Abbr.": st.column_config.TextColumn("Abbr.", help="Abreviação"),
                "V": st.column_config.NumberColumn("V", help="Vitórias", format="%d", width="small"),
                "D": st.column_config.NumberColumn("D", help="Derrotas", format="%d", width="small"),
                "E": st.column_config.NumberColumn("E", help="Empates", format="%d", width="small"),
                "PCT": st.column_config.TextColumn("PCT", help="Percentual de Vitória"),
            }
        )


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
        # Retorna None para a semana atual em caso de erro da API
        st.warning(f"⚠️ Não foi possível carregar a semana atual da ESPN: {e}")
        return None, []

# --- CARREGAMENTO PRINCIPAL ---
historical_data = load_historical_events_from_nflverse(CURRENT_PFR_YEAR)


# --- APLICAÇÃO PRINCIPAL ---

# NOVO DESIGN: Título principal
st.markdown(
    f"<h1 style='color: #4CAF50;'>🏈 Dashboard Histórico NFL {CURRENT_PFR_YEAR}</h1>", 
    unsafe_allow_html=True
)
st.markdown(f"**Fonte de dados:** ESPN (Semana Atual) e **NFLverse** (Resultados Históricos para {CURRENT_PFR_YEAR})")

# 1. Carrega dados da ESPN para saber a semana atual
current_week_espn, live_events = load_live_events_from_espn()

if historical_data.empty:
    st.error("Não foi possível carregar o calendário histórico do NFLverse. Verifique se o ano está correto ou se a URL de dados mudou.")
else:
    # 2. Exibe o placar
    st.markdown("---")
    display_scoreboard(historical_data, current_week_espn)
    
    # NOVO: Calcula e exibe a classificação
    standings_data = calculate_standings(historical_data)

    st.markdown("---")
    st.header("🏆 Classificação da Temporada")
    
    # Exibe em colunas para uma melhor visualização lado a lado
    col_afc, col_nfc = st.columns(2)
    
    with col_afc:
        display_standings(standings_data, 'AFC')
    
    with col_nfc:
        display_standings(standings_data, 'NFC')


    # 3. Adiciona um filtro de semana caso o usuário queira ver outras semanas
    st.markdown("---")
    st.header("Explorar Outras Semanas")

    all_weeks = sorted(historical_data['Week'].unique())
    
    # Garante que o índice selecionado é válido
    default_index = 0
    # FIX: Verifica se current_week_espn não é None antes de buscar o índice.
    if current_week_espn is not None and current_week_espn in all_weeks: 
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
