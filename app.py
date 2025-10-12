import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse

# Configuração da página
st.set_page_config(
    page_title="NFL 2025 Eventos",
    layout="wide", # Essencial para usar a largura total
    initial_sidebar_state="expanded"
)

# --- 0. INJEÇÃO DE CSS CUSTOMIZADO PARA CENTRALIZAÇÃO E MARGENS ---

# O CSS a seguir busca o bloco principal de conteúdo do Streamlit (classe .block-container) 
# e o restringe a 80% da tela (max-width), centralizando-o com margin: 0 auto.
custom_css = """
<style>
/* Aplica-se ao container principal de conteúdo do Streamlit */
.main {
    padding: 0; /* Remove o padding padrão para melhor controle */
}

/* Centraliza o conteúdo (o bloco que contém todos os seus elementos) */
.block-container {
    padding-top: 2rem; /* Mantém um pequeno padding superior */
    padding-left: 0;
    padding-right: 0;
    max-width: 80% !important; /* Limita o conteúdo a 80% da largura da tela */
    margin: 0 auto; /* Centraliza o bloco automaticamente */
}

/* Ajusta o espaçamento superior se necessário */
header {
    margin-bottom: 0rem;
}

</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)

# --- 1. CONFIGURAÇÃO DA API (LINK ESTÁVEL) ---
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"


# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS ---

def get_league_metadata():
    """Retorna informações estáticas da liga."""
    return 'NFL', '2025'

def get_period_name(period):
    """Mapeia o número do período para o nome do Quarto/Overtime."""
    if period == 1: return "1st Quarter"
    if period == 2: return "2nd Quarter"
    if period == 3: return "3rd Quarter"
    if period == 4: return "4th Quarter"
    if period > 4: return "Overtime"
    return ""

def get_event_data(event):
    """
    Extrai e formata os dados principais de um único evento de forma ultra-robusta.
    """
    
    # Valores de segurança (default)
    data_formatada = "N/A"
    hora_formatada = "N/A"
    status_pt = "N/A"
    winner_team = "A definir"
    detail_status = "N/A" 
    
    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')

        # --- CORREÇÃO DE DATA/HORA (Usando isoparse) ---
        if date_iso:
            try:
                dt_utc = isoparse(date_iso) 
                dt_brt = dt_utc - pd.Timedelta(hours=3) # Converte para BRT (UTC-3)

                data_formatada = dt_brt.strftime('%d/%m/%Y')
                hora_formatada = dt_brt.strftime('%H:%M') + ' BRT'
            except Exception:
                pass 
        # --- FIM DA CORREÇÃO DE DATA/HORA ---

        # Extração do Status Principal
        status_type = comp.get('status', {}).get('type', {})
        status_en = status_type.get('description')
        
        status_map = {
            'Final': 'Finalizado',
            'Final/OT': 'Finalizado (OT)',
            'In Progress': 'Em Andamento',
            'Scheduled': 'Agendado'
        }
        status_pt = status_map.get(status_en, status_en)
        
        # Tentativa de extração do Detalhe Status da API
        detail_status_raw = comp.get('status', {}).get('detail')
        if detail_status_raw:
            detail_status = detail_status_raw
        
        # --- LÓGICA DE CORREÇÃO/CONSTRUÇÃO DO DETALHE STATUS (Fallback) ---
        if status_pt == 'Em Andamento' and (detail_status == 'N/A' or not detail_status_raw):
            clock = comp.get('status', {}).get('displayClock', '')
            period_num = comp.get('status', {}).get('period', 0)
            period_name = get_period_name(period_num)
            
            if clock and period_name:
                detail_status = f"{clock} - {period_name}"
            elif status_type.get('shortDetail'):
                # Último fallback, usando shortDetail (ex: "Q3")
                detail_status = status_type.get('shortDetail', 'Em Andamento')
        elif detail_status == 'N/A' and status_type.get('shortDetail'):
             # Para outros status sem detail, o shortDetail pode ser melhor que N/A
            detail_status = status_type.get('shortDetail', 'N/A')
        
        
        # 2. Extração dos times e scores
        competitors = comp.get('competitors', [])
        home_team = {} 
        away_team = {} 

        if len(competitors) >= 2:
            c1 = competitors[0]
            c2 = competitors[1]
            
            c1 = c1 if isinstance(c1, dict) else {}
            c2 = c2 if isinstance(c2, dict) else {}

            if c1.get('homeAway') == 'home':
                home_team = c1
                away_team = c2
            elif c2.get('homeAway') == 'home':
                home_team = c2
                away_team = c1
            else:
                home_team = c1
                away_team = c2
                
        # Extração de Scores e Nomes
        home_score = home_team.get('score', {}).get('displayValue', '0')
        away_score = away_team.get('score', {}).get('displayValue', '0')
        
        home_display_name = home_team.get('team', {}).get('displayName', 'Time Casa')
        away_display_name = away_team.get('team', {}).get('displayName', 'Time Visitante')
            
        # Determinação do Vencedor
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
            'Visitante': away_display_name,
            'Vencedor': winner_team,
            'Score Casa': home_score,
            'Score Visitante': away_score,
            'Detalhe Status': detail_status
        }
        
    except Exception as e:
        # Linha de ERRO para garantir que o app não quebre
        return {
            'Jogo': 'Erro de Estrutura de Dados',
            'Data': 'N/A',
            'Hora': 'N/A',
            'Status': 'ERRO',
            'Casa': 'ERRO DE PROCESSAMENTO',
            'Visitante': 'ERRO DE PROCESSAMENTO',
            'Vencedor': 'N/A',
            'Score Casa': 'N/A',
            'Score Visitante': 'N/A',
            'Detalhe Status': f'Falha na extração: {type(e).__name__}'
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca e normaliza os dados da API de Events da ESPN (2025)."""
    
    st.info(f"Buscando eventos da NFL 2025 (URL: {api_url})...")
    
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

    events_list = data.get('events', [])
    
    if not events_list:
        st.info("Nenhum evento encontrado na API de Events para 2025.")
        return pd.DataFrame()
        
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    df = pd.DataFrame(events_data)
    return df


# --- 3. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    league_name, current_season = get_league_metadata()
    
    st.title(f"🏈 Dashboard {league_name} - {current_season}")
    st.markdown("---")
    
    # A sidebar permanece inalterada
    st.sidebar.header("Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
    st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Recarregar Dados Agora"):
        st.rerun() 
        
    df_events = load_data()

    if df_events.empty:
        st.warning("Não foi possível carregar os dados. Verifique a API.")
        return

    # --- MÉTRICAS (KPIS) ---
    st.header("Visão Geral do Status dos Jogos")
    
    status_counts = df_events['Status'].value_counts()
    
    total_games = len(df_events)
    finalizados = status_counts.get('Finalizado', 0) + status_counts.get('Finalizado (OT)', 0)
    em_andamento = status_counts.get('Em Andamento', 0)
    agendados = status_counts.get('Agendado', 0)
    erros = status_counts.get('ERRO', 0)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total de Jogos", total_games)
    col2.metric("Finalizados", finalizados)
    col3.metric("Em Andamento", em_andamento)
    col4.metric("Agendados", agendados)
    col5.metric("Erros de Extração", erros)

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
        results_df = df_finalized[['Data', 'Hora', 'Jogo', 'Vencedor', 'Score Casa', 'Score Visitante', 'Detalhe Status']].copy()
        
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
            df_scheduled[['Data', 'Hora', 'Jogo', 'Casa', 'Visitante', 'Detalhe Status']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo agendado para o período do Scoreboard.")


if __name__ == '__main__':
    main()
