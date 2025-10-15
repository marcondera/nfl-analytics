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

# FORÇADO PARA 2025, conforme solicitado pelo usuário.
# OBS: O PFR pode não ter o calendário completo de 2025/2026.
CURRENT_PFR_YEAR = 2025 

st.set_page_config(page_title=f"🏈 NFL Dashboard Histórico {CURRENT_PFR_YEAR}", layout="wide", page_icon="🏈")

# Endpoints
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
PFR_URL_TEMPLATE = f"https://www.pro-football-reference.com/years/{CURRENT_PFR_YEAR}/games.htm"

# Mapa de Logos e Abbr para PFR (necessário para mapear nomes do PFR para logos da ESPN)
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "pit": "pit", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

# Mapeamento de nomes completos/curtos do PFR para abreviações da ESPN (ajuste conforme necessário)
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

def normalize_team_name(name):
    """Converte o nome do time PFR em abreviação ESPN."""
    name_str = str(name).strip()
    return PFR_ABBR_MAP.get(name_str, name_str)

@st.cache_data(ttl=3600)
def load_historical_events_from_pfr(year):
    """
    Carrega o histórico de eventos (jogos) do Pro-Football-Reference (PFR).
    
    A tabela de jogos do PFR é frequentemente 'escondida' dentro de comentários HTML
    para permitir funcionalidade de JavaScript, o que quebra o pd.read_html direto.
    Esta função usa regex para "descomentar" o bloco da tabela antes de lê-lo,
    resolvendo o erro de 'list index out of range'.
    """
    
    pfr_url = f"https://www.pro-football-reference.com/years/{year}/games.htm"
    st.info(f"Tentando carregar dados históricos do PFR para o ano: **{year}** a partir de `{pfr_url}`. Aguarde...")

    try:
        # 1. Busca o HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(pfr_url, headers=headers, timeout=10)
        r.raise_for_status()
        html_content = r.text

        # 2. Usa Regex para encontrar e 'descomentar' a tabela principal ('games')
        # Padrão: Busca qualquer conteúdo dentro de <!-- ... --> que contenha 'id="games"'.
        pattern = re.compile(r'<!--(.*?)-->', re.DOTALL)
        
        tables_html = None
        
        # Itera sobre todos os blocos comentados para encontrar o que contém a tabela 'games'
        for match in pattern.findall(html_content):
            if 'id="games"' in match:
                tables_html = match
                break
        
        if not tables_html:
            st.warning("Não foi possível encontrar a tabela de jogos ('games') dentro dos comentários do PFR. O calendário pode não ter sido publicado para este ano, ou o formato mudou.")
            return pd.DataFrame()

        # 3. Lê o HTML descomentado
        # Usamos StringIO para tratar a string como um arquivo
        df_list = pd.read_html(StringIO(tables_html))
        
        # Assumindo que a primeira tabela válida na lista é a de jogos
        if df_list:
            df = df_list[0]
            
            # Limpeza e preparação dos dados
            df.columns = ['_'.join(col).strip() for col in df.columns.values]
            df.columns = [col.replace('Unnamed: 0_level_0_', '').replace('Unnamed: 1_level_0_', '') for col in df.columns]

            # Filtra linhas de cabeçalho repetidas
            df = df[df['Week'] != 'Week'].copy()
            
            # Renomeia colunas para melhor clareza
            df = df.rename(columns={
                'Week': 'Week',
                'Day': 'Day',
                'Date': 'Date',
                'Time': 'Time',
                'Winner': 'Winner_PFR',
                'Loser': 'Loser_PFR',
                'Pts.1': 'Winner_Pts',
                'Pts.2': 'Loser_Pts',
                'Boxscore': 'Boxscore', # Coluna de link
            })
            
            # Converte Week para numérico
            df['Week'] = pd.to_numeric(df['Week'], errors='coerce').astype('Int64')
            df = df.dropna(subset=['Week']) # Remove linhas sem semana (ex: cabeçalhos)

            # Normaliza nomes de times para abreviações da ESPN
            df['Winner_Abbr'] = df['Winner_PFR'].apply(normalize_team_name)
            df['Loser_Abbr'] = df['Loser_PFR'].apply(normalize_team_name)

            # Cria coluna de Data/Hora completa
            df['Date_Full'] = df['Date'] + ' ' + str(year)

            # Limpa colunas desnecessárias e define a ordem
            df = df[['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts', 'Boxscore']]
            
            st.success(f"Dados históricos da Semana {df['Week'].max()} carregados com sucesso do PFR para {year}.")
            return df
        else:
            st.error("Erro: pd.read_html não encontrou tabelas após o parsing do PFR.")
            return pd.DataFrame()

    except requests.exceptions.HTTPError as he:
        if he.response.status_code == 404:
            st.error(f"Erro 404: A página do PFR para o ano {year} não foi encontrada. O calendário pode ainda não ter sido publicado.")
        else:
            st.error(f"Erro HTTP ao carregar PFR para {year}: {he}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro carregando eventos históricos do PFR: {e}. Verifique o formato da tabela do PFR.")
        return pd.DataFrame()

# --- CARREGAMENTO DE DADOS (PFR) ---
historical_data = load_historical_events_from_pfr(CURRENT_PFR_YEAR)


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
    """Exibe o placar formatado com base nos dados históricos do PFR."""

    if df_pfr.empty:
        st.warning("Não há dados históricos disponíveis para exibição.")
        return

    # Usar a semana mais alta disponível nos dados PFR se o ESPN não retornar
    if current_week_espn:
        st.subheader(f"🏈 Calendário da Temporada {CURRENT_PFR_YEAR} (Semana {current_week_espn} - ESPN)")
        df_display = df_pfr[df_pfr['Week'] == current_week_espn].copy()
    else:
        max_week = df_pfr['Week'].max()
        st.subheader(f"🏈 Calendário da Temporada {CURRENT_PFR_YEAR} (Semana {max_week} - PFR)")
        df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    
    # Prepara o DataFrame para exibição
    df_display['Vencedor'] = df_display.apply(
        lambda row: f"{row['Winner_PFR']} ({int(row['Winner_Pts'])})", axis=1
    )
    df_display['Perdedor'] = df_display.apply(
        lambda row: f"{row['Loser_PFR']} ({int(row['Loser_Pts'])})", axis=1
    )
    df_display['Placar'] = df_display['Vencedor'] + ' vs ' + df_display['Perdedor']
    
    # Colunas para visualização simplificada
    games_list = df_display[['Week', 'Date_Full', 'Placar', 'Winner_Abbr', 'Loser_Abbr']].to_dict('records')

    if not games_list:
        st.info(f"Nenhum jogo encontrado para esta semana na base de dados histórica.")
        return

    # Layout de cards para melhor visualização
    cols = st.columns(min(len(games_list), 3)) 
    
    for i, game in enumerate(games_list):
        with cols[i % 3]:
            winner_abbr = game['Winner_Abbr']
            loser_abbr = game['Loser_Abbr']
            
            # Card com estilização básica
            st.markdown(
                f"""
                <div style="
                    border: 2px solid #ccc; 
                    border-radius: 12px; 
                    padding: 15px; 
                    margin-bottom: 15px;
                    background-color: #f8f8f8;
                    box-shadow: 4px 4px 8px rgba(0,0,0,0.1);
                ">
                    <p style="font-size: 1.1em; font-weight: bold; margin-bottom: 5px;">
                        Semana {game['Week']}
                    </p>
                    <p style="font-size: 0.9em; color: #555; margin-bottom: 10px;">
                        {game['Date_Full']}
                    </p>
                    <div style="display: flex; justify-content: space-around; align-items: center;">
                        <div style="text-align: center;">
                            <img src="{get_logo_url(winner_abbr)}" width="50">
                            <p style="font-weight: bold; margin-top: 5px; color: green;">{winner_abbr}</p>
                        </div>
                        <span style="font-weight: bold; font-size: 1.2em;">VENCEU</span>
                        <div style="text-align: center;">
                            <img src="{get_logo_url(loser_abbr)}" width="50">
                            <p style="font-weight: bold; margin-top: 5px; color: red;">{loser_abbr}</p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# --- APLICAÇÃO PRINCIPAL ---

st.title(f"🏈 Dashboard Histórico NFL {CURRENT_PFR_YEAR}")
st.markdown(f"**Fonte de dados:** ESPN (Semana Atual) e Pro-Football-Reference (Resultados Históricos para {CURRENT_PFR_YEAR})")

# 1. Carrega dados da ESPN para saber a semana atual
current_week_espn, live_events = load_live_events_from_espn()

if historical_data.empty:
    st.error("Não foi possível carregar o calendário histórico do PFR. O ano pode estar incorreto, ou a estrutura da página mudou.")
else:
    # 2. Exibe o placar
    display_scoreboard(historical_data, current_week_espn)

# 3. Adiciona um filtro de semana caso o usuário queira ver outras semanas
if not historical_data.empty:
    all_weeks = sorted(historical_data['Week'].unique())
    
    st.markdown("---")
    st.header("Explorar Outras Semanas")

    selected_week = st.selectbox(
        'Selecione a Semana para Visualizar:',
        options=all_weeks,
        index=all_weeks.index(current_week_espn) if current_week_espn in all_weeks else (len(all_weeks) -1 if all_weeks else 0)
    )

    if selected_week is not None:
        df_selected_week = historical_data[historical_data['Week'] == selected_week].copy()
        
        if not df_selected_week.empty:
            st.subheader(f"Resultados da Semana {selected_week} ({CURRENT_PFR_YEAR})")
            
            # Prepara a tabela de visualização
            df_selected_week['Placar Final'] = df_selected_week.apply(
                lambda row: f"{row['Winner_PFR']} {int(row['Winner_Pts'])} - {int(row['Loser_Pts'])} {row['Loser_PFR']}", 
                axis=1
            )
            
            df_final_view = df_selected_week[[
                'Date_Full', 
                'Placar Final',
            ]].rename(columns={'Date_Full': 'Data'})
            
            st.dataframe(
                df_final_view, 
                hide_index=True, 
                use_container_width=True
            )
        else:
            st.info(f"Nenhum jogo encontrado na base de dados histórica para a Semana {selected_week} de {CURRENT_PFR_YEAR}.")
