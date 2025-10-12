import streamlit as st
import pandas as pd
import json
from datetime import datetime
import os

# Configuração da página
st.set_page_config(
    page_title="NFL Dashboard 2025",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. FUNÇÕES DE PROCESSAMENTO DE DADOS ---

def get_event_data(event):
    """Extrai e formata os dados principais de um único evento."""
    
    # Tentativa de acesso seguro à competição (geralmente há apenas 1)
    try:
        comp = event['competitions'][0]
    except (KeyError, IndexError):
        return None

    # Mapeamento do Status (Tradução)
    status_en = comp['status']['type']['description']
    status_map = {
        'Final': 'Finalizado',
        'Final/OT': 'Finalizado (OT)',
        'In Progress': 'Em Andamento',
        'Scheduled': 'Agendado'
    }
    status_pt = status_map.get(status_en, status_en)
    
    # Extração de informações de hora
    date_iso = comp['date']
    try:
        # Converte a data/hora ISO 8601 (Z = Zulu/UTC) para o fuso horário de Brasília (UTC-3)
        dt_utc = datetime.strptime(date_iso, '%Y-%m-%dT%H:%M:%SZ')
        # Ajuste simples para UTC-3 (considerando que não estamos tratando daylight saving complexo)
        dt_brt = dt_utc.replace(tzinfo=None) - pd.Timedelta(hours=3)
        data_formatada = dt_brt.strftime('%d/%m/%Y')
        hora_formatada = dt_brt.strftime('%H:%M') + ' BRT'
    except ValueError:
        data_formatada = date_iso.split('T')[0]
        hora_formatada = "N/A"

    # Extração de competidores (Home e Away)
    competitors = comp['competitors']
    home_team = next((c for c in competitors if c['homeAway'] == 'home'), competitors[0])
    away_team = next((c for c in competitors if c['homeAway'] == 'away'), competitors[1])

    # Extração de Scores (trata caso de jogo agendado onde o score é None/missing)
    home_score = home_team.get('score', {}).get('displayValue', '0')
    away_score = away_team.get('score', {}).get('displayValue', '0')
    
    # Determina o Vencedor (apenas para jogos finalizados)
    winner_team = "A definir"
    if status_pt.startswith('Finalizado'):
        if float(home_score) > float(away_score):
            winner_team = home_team['team']['abbreviation']
        elif float(away_score) > float(home_score):
            winner_team = away_team['team']['abbreviation']
        else:
            winner_team = "Empate"

    return {
        'Jogo': event.get('name', 'N/A'),
        'Data': data_formatada,
        'Hora': hora_formatada,
        'Status': status_pt,
        'Casa': home_team['team']['displayName'],
        'Score Casa': home_score,
        'Visitante': away_team['team']['displayName'],
        'Score Visitante': away_score,
        'Vencedor': winner_team,
        'Detalhe Status': comp['status']['detail']
    }


@st.cache_data
def load_data(file_path="events.json"):
    """Carrega e normaliza os dados do arquivo JSON."""
    if not os.path.exists(file_path):
        st.error(f"Arquivo '{file_path}' não encontrado. Certifique-se de que ele está na raiz do seu repositório.")
        return pd.DataFrame()

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Processa cada evento para extrair os dados
    events_data = [get_event_data(e) for e in data.get('events', [])]
    
    # Remove eventos que falharam na extração
    events_data = [item for item in events_data if item is not None]

    if not events_data:
        st.warning("Não foi possível extrair dados válidos dos eventos.")
        return pd.DataFrame()
        
    df = pd.DataFrame(events_data)
    return df


# --- 2. LAYOUT DO DASHBOARD STREAMLIT ---

def main():
    st.title("🏈 Dashboard NFL - Eventos da API")
    st.markdown("---")

    df_events = load_data()

    if df_events.empty:
        return

    # --- MÉTRICAS (KPIS) ---
    st.header("Visão Geral do Status dos Jogos")
    
    # Calcula os KPIs
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
    
    # 1. Jogos em Andamento
    st.header("🔴 Jogos Atuais (Em Andamento)")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        st.dataframe(
            df_in_progress[['Jogo', 'Data', 'Hora', 'Detalhe Status', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo em andamento no momento.")


    # 2. Próximos Jogos Agendados
    st.header("📅 Próximos Jogos Agendados")
    df_scheduled = df_events[df_events['Status'] == 'Agendado'].sort_values(by='Data')
    
    if not df_scheduled.empty:
        st.dataframe(
            df_scheduled[['Jogo', 'Data', 'Hora', 'Detalhe Status', 'Casa', 'Visitante']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo agendado.")
        
    st.markdown("---")

    # 3. Resultados Recentes (Finalizados)
    st.header("✅ Resultados (Finalizados)")
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado')].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        # Colunas customizadas para a tabela de resultados
        results_df = df_finalized[['Data', 'Jogo', 'Vencedor', 'Score Casa', 'Score Visitante', 'Detalhe Status']].copy()
        
        st.dataframe(
            results_df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum resultado finalizado encontrado.")


if __name__ == '__main__':
    main()