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
# AJUSTADO: Ano definido para 2025 conforme solicitado.
CURRENT_PFR_YEAR = 2025 

# Configurações iniciais do Streamlit (título, layout)
st.set_page_config(page_title=f"🏈 NFL Dashboard Histórico {CURRENT_PFR_YEAR}", layout="wide", page_icon="🏈")

# Endpoints
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
# Nova URL de dados históricos - fonte mais robusta e estável (nflverse/nfldata é o repo atualizado)
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

# Mapeamento reverso para obter nomes de exibição (ex: 'BUF' -> 'Bills')
PFR_NAME_MAP_REVERSE = {
    v: k for k, v in PFR_ABBR_MAP.items() 
    if len(k.split()) == 1 or v == k.split()[-1]
}

# NOVO: Mapeamento de Conferência e Divisão (2020-presente)
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
    Usa uma fonte de dados mais estável para evitar bloqueios de scraping.
    """
    # NOVO DESIGN: Texto de carregamento estilizado
    st.info(f"⏳ Carregando dados históricos do NFLverse para a temporada: **{year}** a partir de `{NFLVERSE_GAMES_URL}`. Aguarde...")

    try:
        # Lê o CSV diretamente da URL
        df = pd.read_csv(NFLVERSE_GAMES_URL)
        
        # Filtra pelo ano (season) e apenas jogos da temporada regular ('REG')
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        
        # NOVO FILTRO: Garante que apenas jogos JOGADOS (com scores > 0) sejam considerados.
        df_year = df_year[(df_year['home_score'].fillna(0) > 0) | (df_year['away_score'].fillna(0) > 0)].copy()

        if df_year.empty:
            st.warning(f"Nenhum jogo jogado encontrado no NFLverse para a temporada {year}.")
            return pd.DataFrame()

        # Cria as colunas de Vencedor/Perdedor e Placar, mantendo a estrutura esperada pelo Dashboard
        
        # Cria um mapeamento simples de ABBR para um nome completo simulado
        ABBR_TO_NAME = {v: k for k, v in PFR_ABBR_MAP.items() if v == k.split()[-1] or v == k}
            
        def calculate_result(row):
            winner_abbr, loser_abbr, winner_pts, loser_pts = None, None, 0, 0
            
            home_score = int(row['home_score']) if pd.notna(row['home_score']) else 0
            away_score = int(row['away_score']) if pd.notna(row['away_score']) else 0
            
            if home_score > away_score:
                winner_abbr, winner_pts = row['home_team'], home_score
                loser_abbr, loser_pts = row['away_team'], away_score
            elif away_score > home_score:
                winner_abbr, winner_pts = row['away_team'], away_score
                loser_abbr, loser_pts = row['home_team'], home_score
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
        
    except requests.exceptions.RequestException as he:
        st.error(f"❌ Erro de rede ao carregar NFLverse: {he}. Verifique a conectividade ou a URL de dados.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro carregando e processando eventos do NFLverse: {e}")
        return pd.DataFrame()


# --- FUNÇÕES DE CLASSIFICAÇÃO (STANDINGS) ---

def calculate_standings(df_games):
    """Calcula Vitórias, Derrotas, Empates e PCT para cada time."""
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
            # Caso raro, mas para garantir a consistência
            standings[winner_abbr]['L'] += 1
            standings[loser_abbr]['W'] += 1
        else: # Empate (Tie)
            standings[winner_abbr]['T'] += 1
            standings[loser_abbr]['T'] += 1

    df_standings = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Abbr'})
    
    # Adiciona Conferência e Divisão
    df_standings['Conf'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('conf', 'N/A'))
    df_standings['Div'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('div', 'N/A'))
    
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
        
        # Renomear e estilizar
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


# --- FUNÇÃO DE BUSCA E VISUALIZAÇÃO DE PLACAR ---

def display_scoreboard(df_pfr, current_week_espn=None):
    """Exibe o placar formatado com o novo design."""

    if df_pfr.empty:
        st.warning("Não há dados históricos disponíveis para exibição.")
        return

    # Lógica de determinação da semana para o cabeçalho
    if current_week_espn:
        st.subheader(f"🗓️ Jogos da Semana {current_week_espn}")
        df_display = df_pfr[df_pfr['Week'] == current_week_espn].copy()
    else:
        max_week = df_pfr['Week'].max()
        st.subheader(f"🗓️ Última Semana Jogada ({max_week})")
        df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    
    # Prepara o DataFrame para exibição
    df_display['Winner_Pts'] = pd.to_numeric(df_display['Winner_Pts'], errors='coerce').fillna(0).astype(int)
    df_display['Loser_Pts'] = pd.to_numeric(df_display['Loser_Pts'], errors='coerce').fillna(0).astype(int)

    games_list = df_display[['Week', 'Date_Full', 'Winner_Abbr', 'Loser_Abbr', 'Winner_Pts', 'Loser_Pts']].to_dict('records')

    if not games_list:
        st.info(f"Nenhum jogo encontrado para esta semana na base de dados histórica.")
        return

    # Layout de cards para melhor visualização (Rebranding)
    
    cols = st.columns(min(len(games_list), 3)) 
    
    for i, game in enumerate(games_list):
        with cols[i % 3]:
            winner_abbr = game['Winner_Abbr']
            loser_abbr = game['Loser_Abbr']
            winner_pts = game['Winner_Pts']
            loser_pts = game['Loser_Pts']

            status_text = "FINALIZADO"
            
            # NOVO DESIGN DE CARD
            st.markdown(
                f"""
                <div style="
                    border: 1px solid #333; 
                    border-radius: 8px; 
                    padding: 15px; 
                    margin-bottom: 20px;
                    background-color: #1E2129; /* Fundo mais escuro */
                    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                    color: #F0F2F6;
                    text-align: center;
                ">
                    <p style="font-size: 0.9em; color: #8D99AE; margin-bottom: 10px;">
                        SEMANA {game['Week']} | {game['Date_Full']}
                    </p>
                    <div style="display: flex; justify-content: space-around; align-items: center;">
                        
                        <!-- VENCEDOR -->
                        <div style="text-align: center; flex: 1; padding: 0 5px; border-right: 1px dashed #333;">
                            <img src="{get_logo_url(winner_abbr)}" width="55" style="border-radius: 5px; margin-bottom: 5px;">
                            <p style="font-weight: bold; font-size: 1.1em; color: #4CAF50;">{winner_abbr}</p>
                            <span style="font-size: 1.8em; font-weight: 900; color: #4CAF50;">{winner_pts}</span>
                        </div>
                        
                        <span style="font-weight: 900; font-size: 1.0em; color: #8D99AE; margin: 0 10px;">@</span>
                        
                        <!-- PERDEDOR -->
                        <div style="text-align: center; flex: 1; padding: 0 5px; border-left: 1px dashed #333;">
                            <img src="{get_logo_url(loser_abbr)}" width="55" style="border-radius: 5px; margin-bottom: 5px;">
                            <p style="font-weight: bold; font-size: 1.1em; color: #FF4B4B;">{loser_abbr}</p>
                            <span style="font-size: 1.8em; font-weight: 900; color: #FF4B4B;">{loser_pts}</span>
                        </div>
                    </div>
                     <p style="font-size: 0.8em; font-weight: 600; margin-top: 15px; color: #8D99AE;">
                        {status_text}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

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
        st.error(f"❌ Erro carregando dados em tempo real da ESPN: {e}")
        return None, []

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
