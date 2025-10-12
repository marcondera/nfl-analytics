import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 

# Configuração da página
st.set_page_config(
    page_title="NFL Scoreboard Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. CONFIGURAÇÃO DAS APIS (AGORA APONTANDO PARA 2025) ---
# Para buscar uma semana específica, usamos o formato: ?seasontype=2&season=2025&week=6
# SeasonType 2 é para temporada regular.
API_URL_SCOREBOARD_BASE = "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
API_URL_SCOREBOARD_2025 = f"{API_URL_SCOREBOARD_BASE}?seasontype=2&season=2025&week=6"
API_URL_LEAGUE_METADATA = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"

# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS (SEM CACHE) ---

def get_league_metadata(api_url=API_URL_LEAGUE_METADATA):
    """Busca informações estáticas da liga (nome e ano da temporada)."""
    try:
        response = requests.get(api_url)
        response.raise_for_status() 
        data = response.json()
        
        league_name = data.get('name', 'NFL')
        
        # Tenta extrair o ano da temporada
        season_ref = data.get('season', {}).get('$ref')
        current_year = "2025" # Padrão para 2025, conforme solicitado
        if season_ref:
            parts = season_ref.split('/')
            current_year = parts[-1].split('?')[0]
            
        return league_name, current_year
    except Exception:
        return 'NFL', '2025'


def get_event_data(event):
    """Extrai e formata os dados principais de um único evento."""
    
    try:
        comp = event['competitions'][0]
    except (KeyError, IndexError):
        return None

    # Mapeamento e Tradução do Status
    status_type = comp['status'].get('type', {})
    status_en = status_type.get('description')
    
    status_map = {
        'Final': 'Finalizado',
        'Final/OT': 'Finalizado (OT)',
        'In Progress': 'Em Andamento',
        'Scheduled': 'Agendado'
    }
    status_pt = status_map.get(status_en, status_en)
    
    # Formatação de Data e Hora (Ajuste para BRT = UTC-3)
    date_iso = comp['date']
    try:
        dt_utc = datetime.strptime(date_iso, '%Y-%m-%dT%H:%M:%SZ')
        dt_brt = dt_utc.replace(tzinfo=None) - pd.Timedelta(hours=3)
        data_formatada = dt_brt.strftime('%d/%m/%Y')
        hora_formatada = dt_brt.strftime('%H:%M') + ' BRT'
    except Exception:
        data_formatada = "N/A"
        hora_formatada = "N/A"


    # --- EXTRAÇÃO ULTRA-ROBUSTA DE COMPETIDORES: ELIMINA ATTRIBUTEERROR ---
    competitors = comp.get('competitors', [])
    home_team = {} 
    away_team = {} 

    # Lógica explícita if/else para garantir que home_team/away_team sejam sempre dicionários
    if len(competitors) >= 2:
        c1 = competitors[0]
        c2 = competitors[1]
        
        # Garantindo que c1 e c2 são dicionários
        if not isinstance(c1, dict): c1 = {}
        if not isinstance(c2, dict): c2 = {}

        if c1.get('homeAway') == 'home':
            home_team = c1
            away_team = c2
        elif c2.get('homeAway') == 'home':
            home_team = c2
            away_team = c1
        else:
            # Fallback posicional se 'homeAway' não for definido, assumindo ordem padrão
            home_team = c1
            away_team = c2
            
    # Extração de Scores e Nomes (AGORA SEGURO)
    home_score = home_team.get('score', {}).get('displayValue', '0')
    away_score = away_team.get('score', {}).get('displayValue', '0')
    
    home_display_name = home_team.get('team', {}).get('displayName', 'Time Casa')
    away_display_name = away_team.get('team', {}).get('displayName', 'Time Visitante')
        
    # Determinação do Vencedor
    winner_team = "A definir"
    if status_pt.startswith('Finalizado'):
        try:
            if home_score.isdigit() and away_score.isdigit():
                 if float(home_score) > float(away_score):
                    winner_team = home_team.get('team', {}).get('abbreviation', home_display_name)
                 elif float(away_score) > float(home_score):
                    winner_team = away_team.get('team', {}).get('abbreviation', away_display_name)
                 else:
                    winner_team = "Empate"
            else:
                winner_team = "N/A"
        except Exception:
            winner_team = "N/A"


    return {
        'Jogo': event.get('name', 'N/A'),
        'Data': data_formatada,
        'Hora': hora_formatada,
        'Status': status_pt,
        'Casa': home_display_name,
        'Score Casa': home_score,
        'Visitante': away_display_name,
        'Score Visitante': away_score,
        'Vencedor': winner_team,
        'Detalhe Status': comp['status'].get('detail', 'N/A')
    }


def load_data(api_url=API_URL_SCOREBOARD_2025):
    """Busca e normaliza os dados diretamente da API de Scoreboard da ESPN."""
    
    st.info(f"Buscando placares da NFL 2025 (Semana 6)...")
    
    try:
        response = requests.get(api_url)
        response.raise_for_status() 
        data = response.json()
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar dados da API. Verifique a URL e autenticação: {e}")
        return pd.DataFrame()
    except json.JSONDecodeError:
        st.error("Erro ao decodificar a resposta como JSON.")
        return pd.DataFrame()

    events_list = data.get('events')
    
    if not events_list:
        st.info("Nenhum evento encontrado no Scoreboard da NFL para o período atual (2025).")
        return pd.DataFrame()
        
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    if not events_data:
        st.warning("Não foi possível extrair dados válidos dos eventos após o processamento.")
        return pd.DataFrame()
        
    df = pd.DataFrame(events_data)
    return df


# --- 3. LAYOUT DO DASHBOARD STREAMLIT ---

def main():
    
    league_name, current_season = get_league_metadata()
    
    st.title(f"🏈 Dashboard {league_name} - Placares Atuais")
    st.markdown("---")
    
    # Barra Lateral com Metadados e Controles
    st.sidebar.markdown("### Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
