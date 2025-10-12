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

# --- 1. CONFIGURAÇÃO DAS APIS (USANDO SUA URL ESTÁVEL) ---
# Esta URL é muito mais estável para buscar eventos de uma temporada inteira.
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"
API_URL_LEAGUE_METADATA = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"


# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS (SEM CACHE) ---

def get_league_metadata(api_url=API_URL_LEAGUE_METADATA):
    """Busca informações estáticas da liga."""
    try:
        response = requests.get(api_url)
        response.raise_for_status() 
        data = response.json()
        
        league_name = data.get('name', 'NFL')
        
        # Padrão para 2025, já que a busca é por essa data
        current_year = "2025" 
        
        return league_name, current_year
    except Exception:
        return 'NFL', '2025'


def get_event_data(event):
    """Extrai e formata os dados principais de um único evento."""
    
    try:
        # A API de events usa a mesma estrutura de competitions[0]
        comp = event['competitions'][0]
    except (KeyError, IndexError):
        return None

    # Mapeamento e Tradução do Status
    status_type = comp.get('status', {}).get('type', {})
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


    # --- EXTRAÇÃO ULTRA-ROBUSTA (A ÚLTIMA LINHA DE DEFESA) ---
    competitors = comp.get('competitors', [])
    home_team = {} 
    away_team = {} 

    # Lógica explícita para garantir que home_team/away_team sejam sempre dicionários
    if len(competitors) >= 2:
        c1 = competitors[0]
        c2 = competitors[1]
        
        # Garantindo que c1 e c2 são dicionários (aqui estava o ponto de falha)
        c1 = c1 if isinstance(c1, dict) else {}
        c2 = c2 if isinstance(c2, dict) else {}

        # Tentativa de identificar pelo homeAway (mais confiável)
        if c1.get('homeAway') == 'home':
            home_team = c1
            away_team = c2
        elif c2.get('homeAway') == 'home':
            home_team = c2
            away_team = c1
        else:
            # Fallback posicional, mas com garantia de que são dicionários
            home_team = c1
            away_team = c2
            
    # Extração de Scores e Nomes (AGORA À PROVA DE FALHAS)
    # Garante que .get() seja chamado em um dict ({} ou o time)
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
        'Detalhe Status': comp.get('status', {}).get('detail', 'N/A')
    }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca e normaliza os dados da API de Events da ESPN (2025)."""
    
    st.info(f"Buscando todos os eventos da NFL 2025 (URL: {api_url})...")
    
    try:
        # Nota: A API de partners da ESPN frequentemente requer uma chave 'apikey'. 
        # Se falhar aqui, o problema pode ser a falta dessa chave.
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
        st.info("Nenhum evento encontrado na API de Events para 2025.")
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
    
    st.title(f"🏈 Dashboard {league_name} - Todos os Eventos de {current_season}")
    st.markdown("---")
    
    # Barra Lateral com Metadados e Controles
    st.sidebar.markdown("### Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
    st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Recarregar Dados Agora"):
        st.rerun() 
        
    # Busca dados do Scoreboard
    df_events = load_data()

    if df_events.empty:
        return

    # --- MÉTRICAS (KPIS) ---
    st.header("Visão Geral do Status dos Jogos")
    
    status_counts = df_events['Status'].value_counts()
    
    total_games = len(df_events)
    finalizados = status_counts.get('Finalizado', 0) + status_counts.get('Finalizado (OT)', 0)
    em_andamento = status_counts.get('Em Andamento', 0)
    agendados = status_counts.get('Agendado', 0)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Jogos", total_games)
    col2.metric("Finalizados", finalizados)
    col3.metric("Em Andamento", em_andamento)
    col4.metric("Agendados", agendados)

    st.markdown("---")

    # --- TABELAS DETALHADAS ---
    
    # 1. Jogos em Andamento (Ao Vivo)
    st.header("🔴 Jogos Ao Vivo")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        st.dataframe(
            df_in_progress[['Jogo', 'Detalhe Status', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo em andamento no momento.")


    # 2. Resultados Recentes (Finalizados)
    st.header("✅ Resultados Finais")
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado', na=False)].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        results_df = df_finalized[['Data', 'Jogo', 'Vencedor', 'Score Casa', 'Score Visitante']].copy()
        
        st.dataframe(
            results_df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum resultado finalizado encontrado.")

    # 3. Próximos Jogos Agendados
    st.header("📅 Próximos Jogos")
    df_scheduled = df_events[df_events['Status'] == 'Agendado'].sort_values(by=['Data', 'Hora'])
    
    if not df_scheduled.empty:
        st.dataframe(
            df_scheduled[['Data', 'Hora', 'Jogo', 'Casa', 'Visitante']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo agendado para o período do Scoreboard.")


if __name__ == '__main__':
    main()
