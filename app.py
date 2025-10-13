import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests
from dateutil.parser import isoparse

# Configuração da página
st.set_page_config(
    page_title="NFL Results Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 1. CONFIGURAÇÃO DE LOGOS E API ---

API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "det": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "tb": "tb", "TEN": "ten",
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh", "TB": "tb", "DET": "det"
}

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(abbreviation.upper(), abbreviation.lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

# --- 2. FUNÇÕES DE PROCESSAMENTO DE DADOS ---

def get_period_name(period):
    period_map = {
        1: "1º Quarto",
        2: "2º Quarto",
        3: "3º Quarto",
        4: "4º Quarto"
    }
    return period_map.get(period, "Prorrogação" if period > 4 else "")

def get_event_data(event):
    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')

        # Formatar data e horário
        data_formatada = "N/A"
        if date_iso:
            dt_utc = isoparse(date_iso)
            dt_brt = dt_utc - pd.Timedelta(hours=3)
            data_formatada = dt_brt.strftime('%d/%m/%Y %H:%M BRT')

        status = comp.get('status', {})
        status_type = status.get('type', {})
        status_text_check = str(status_type).lower()

        # Mapeamento de status
        if 'final' in status_text_check:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in status_text_check else 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
            status_pt = status_type.get('description', 'Status Desconhecido')

        # Resultado e competidores
        competitors = comp.get('competitors', [])
        home_team, away_team = (competitors + [None, None])[:2]

        home_abbr = home_team.get('team', {}).get('abbreviation', 'CASA') if home_team else "CASA"
        away_abbr = away_team.get('team', {}).get('abbreviation', 'FORA') if away_team else "FORA"
        home_score = int(home_team.get('score', {}).get('value', 0)) if home_team else 0
        away_score = int(away_team.get('score', {}).get('value', 0)) if away_team else 0

        winner = (
            home_abbr if home_score > away_score else
            away_abbr if away_score > home_score else
            "Empate"
        )

        return {
            'Jogo': event.get('name', 'N/A'),
            'Data': data_formatada,
            'Status': status_pt,
            'Casa': home_abbr,
            'Visitante': away_abbr,
            'Vencedor': winner,
            'Score Casa': home_score,
            'Score Visitante': away_score,
        }
    except Exception as e:
        return {
            'Jogo': 'Erro de Dados',
            'Data': 'N/A',
            'Status': 'ERRO',
            'Casa': 'ERRO',
            'Visitante': 'ERRO',
            'Vencedor': 'N/A',
            'Score Casa': 0,
            'Score Visitante': 0
        }

def load_data(api_url=API_URL_EVENTS_2025):
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        events = data.get('events', [])
        return pd.DataFrame([get_event_data(event) for event in events])
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# --- 3. FUNÇÕES DE RENDERIZAÇÃO ---

def display_games(df, title):
    st.header(title)
    for _, row in df.iterrows():
        col1, col2, col3 = st.columns([2, 6, 2])
        with col1:
            st.image(get_logo_url(row['Casa']), width=60)
        with col2:
            st.subheader(f"{row['Casa']} vs {row['Visitante']}")
            st.write(f"Status: {row['Status']}")
            st.write(f"Resultado: {row['Resultado']}")
        with col3:
            st.image(get_logo_url(row['Visitante']), width=60)
        st.divider()

# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    st.title("🏈 NFL Results Dashboard")
    st.markdown("### Informações atualizadas sobre jogos da NFL")
    
    df = load_data()
    if df.empty:
        st.error("Erro ao carregar dados. Tente novamente mais tarde.")
        return

    df_in_progress = df[df['Status'] == 'Em Andamento']
    df_scheduled = df[df['Status'] == 'Agendado']
    df_finalized = df[df['Status'].str.startswith('Finalizado')]

    if not df_in_progress.empty:
        display_games(df_in_progress, "🔴 Jogos Ao Vivo")
    if not df_scheduled.empty:
        display_games(df_scheduled, "⏳ Próximos Jogos")
    if not df_finalized.empty:
        display_games(df_finalized, "✅ Resultados Recentes")

if __name__ == '__main__':
    main()
