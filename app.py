import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse

st.set_page_config(
    page_title="NFL Results Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

def get_period_name(period):
    period_map = {1: "1º Quarto", 2: "2º Quarto", 3: "3º Quarto", 4: "4º Quarto"}
    return period_map.get(period, "Prorrogação" if period > 4 else "")

def get_event_data(event):
    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')
        data_formatada = isoparse(date_iso).strftime('%d/%m/%Y %H:%M BRT') if date_iso else "N/A"

        status = comp.get('status', {})
        status_type = status.get('type', {})
        status_text = str(status_type).lower()
        if 'final' in status_text:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in status_text else 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
        else:
            status_pt = 'Agendado' if status_type.get('state') == 'pre' else status_type.get('description', 'Status Desconhecido')

        competitors = comp.get('competitors', [])
        home, away = (competitors + [None, None])[:2]

        home_abbr = home.get('team', {}).get('abbreviation', 'CASA') if home else "CASA"
        away_abbr = away.get('team', {}).get('abbreviation', 'FORA') if away else "FORA"
        home_score = int(home.get('score', {}).get('value', 0)) if home else 0
        away_score = int(away.get('score', {}).get('value', 0)) if away else 0

        winner = home_abbr if home_score > away_score else away_abbr if away_score > home_score else "Empate"

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
    except Exception:
        return {
            'Jogo': 'Erro ao carregar',
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
        events = response.json().get('events', [])
        return pd.DataFrame([get_event_data(event) for event in events])
    except Exception:
        st.error("Erro ao carregar os dados da API.")
        return pd.DataFrame()

def display_games(df, title):
    st.header(title)
    for _, row in df.iterrows():
        col1, col2, col3 = st.columns([2, 6, 2])
        with col1:
            st.image(get_logo_url(row['Casa']), width=60)
        with col2:
            st.markdown(f"### {row['Casa']} **vs** {row['Visitante']}")
            st.write(f"Status: {row['Status']} | Resultado: {row['Score Casa']} - {row['Score Visitante']}")
        with col3:
            st.image(get_logo_url(row['Visitante']), width=60)
        st.divider()

def main():
    st.title("🏈 NFL Results Dashboard")
    st.markdown("### Informações atualizadas sobre jogos da NFL")

    df_events = load_data()
    if df_events.empty:
        st.warning("Nenhum dado disponível.")
        return

    df_in_progress = df_events[df_events['Status'] == 'Em Andamento']
    df_scheduled = df_events[df_events['Status'] == 'Agendado']
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado')]

    if not df_in_progress.empty:
        display_games(df_in_progress, "🔴 Jogos Ao Vivo")
    if not df_scheduled.empty:
        display_games(df_scheduled, "⏳ Próximos Jogos")
    if not df_finalized.empty:
        display_games(df_finalized, "✅ Resultados Recentes")

if __name__ == '__main__':
    main()
