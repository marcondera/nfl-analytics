import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse

# --- CONFIGURAÇÃO DO APP ---
st.set_page_config(
    page_title="NFL Results Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon="🏈"
)

# --- ESTILOS ---
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }

    .winner { color: #4CAF50; font-weight: bold; }
    .loser { color: #FF4B4B; font-weight: normal; }

    .score-display {
        text-align: center;
        font-size: 2.8em;
        font-weight: bold;
        margin: 5px 0;
    }

    .team-names {
        text-align: center;
        font-size: 1.3em;
        font-weight: 500;
        margin-bottom: 5px;
    }

    .live-detail {
        font-size: 1.1em;
        color: #FF4B4B;
        text-align: center;
        margin-top: -10px;
        margin-bottom: 10px;
    }

    .status-discreto {
        font-size: 0.9em;
        color: #6c757d;
        text-align: center;
        margin-top: 5px;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)


API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh"
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

        status_pt = 'Status Desconhecido'
        detalhe_status = ''

        if 'final' in status_text:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in status_text else 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
            clock = status.get('displayClock', '0:00')
            period = status.get('period', 1)
            period_name = get_period_name(period)
            detalhe_status = f"{clock} restantes no {period_name}"
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'

        if status_pt == 'Status Desconhecido':
            status_pt = status_type.get('description', 'Status Desconhecido')

        competitors = comp.get('competitors', [])
        home, away = (competitors + [None, None])[:2]

        home_abbr = home.get('team', {}).get('abbreviation', 'CASA') if home else "CASA"
        away_abbr = away.get('team', {}).get('abbreviation', 'FORA') if away else "FORA"

        home_score = int(home.get('score', {}).get('value', 0)) if home and home.get('score') else 0
        away_score = int(away.get('score', {}).get('value', 0)) if away and away.get('score') else 0

        winner = home_abbr if home_score > away_score else away_abbr if away_score > home_score else "Empate"

        return {
            'Jogo': event.get('name', 'N/A'),
            'Data': data_formatada,
            'Status': status_pt,
            'Detalhe Status': detalhe_status,
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
            'Detalhe Status': '',
            'Casa': 'ERRO',
            'Visitante': 'ERRO',
            'Vencedor': 'N/A',
            'Score Casa': 0,
            'Score Visitante': 0
        }

@st.cache_data(ttl=60)
def load_data(api_url):
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        events = response.json().get('events', [])
        return pd.DataFrame([get_event_data(event) for event in events])
    except Exception:
        st.error("Erro ao carregar os dados da API. Verifique a URL e a conexão.")
        return pd.DataFrame()

# --- EXIBIÇÃO SEM DIVS ---
def display_games(df, title, num_cols=4):
    if df.empty:
        return

    st.header(title)

    for i in range(0, len(df), num_cols):
        chunk = df.iloc[i:i + num_cols]
        chunk = chunk[(chunk['Casa'] != "ERRO") & (chunk['Visitante'] != "ERRO")]
        if chunk.empty:
            continue

        cols = st.columns(len(chunk), gap="large")

        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                casa_nome_tag = f"<span>{row['Casa']}</span>"
                visitante_nome_tag = f"<span>{row['Visitante']}</span>"
                casa_score_tag = f"<span>{row['Score Casa']}</span>"
                visitante_score_tag = f"<span>{row['Score Visitante']}</span>"

                status_jogo = row['Status']
                if status_jogo.startswith('Finalizado'):
                    if row['Vencedor'] == row['Casa']:
                        casa_nome_tag = f"<span class='winner'>{row['Casa']}</span>"
                        casa_score_tag = f"<span class='winner'>{row['Score Casa']}</span>"
                        visitante_nome_tag = f"<span class='loser'>{row['Visitante']}</span>"
                        visitante_score_tag = f"<span class='loser'>{row['Score Visitante']}</span>"
                    elif row['Vencedor'] == row['Visitante']:
                        visitante_nome_tag = f"<span class='winner'>{row['Visitante']}</span>"
                        visitante_score_tag = f"<span class='winner'>{row['Score Visitante']}</span>"
                        casa_nome_tag = f"<span class='loser'>{row['Casa']}</span>"
                        casa_score_tag = f"<span class='loser'>{row['Score Casa']}</span>"

                st.markdown(
                    f"<p class='team-names'>{casa_nome_tag} vs {visitante_nome_tag}</p>",
                    unsafe_allow_html=True
                )

                if status_jogo == 'Em Andamento':
                    st.markdown(
                        f"<p class='live-detail'>🔴 {row['Detalhe Status']}</p>",
                        unsafe_allow_html=True
                    )

                col_home, col_score, col_away = st.columns([1, 2, 1])
                with col_home:
                    st.image(get_logo_url(row['Casa']), width=60)
                with col_score:
                    st.markdown(
                        f"<p class='score-display'>{casa_score_tag} - {visitante_score_tag}</p>",
                        unsafe_allow_html=True
                    )
                with col_away:
                    st.image(get_logo_url(row['Visitante']), width=60)

                if status_jogo == 'Agendado':
                    st.markdown(f"<p class='status-discreto'>Início: {row['Data']}</p>", unsafe_allow_html=True)
                elif status_jogo.startswith('Finalizado'):
                    st.markdown(f"<p class='status-discreto'>{status_jogo}</p>", unsafe_allow_html=True)


# --- MAIN ---
def main():
    st.title("🏈 NFL Results Dashboard")
    st.markdown("### Informações atualizadas sobre jogos da NFL (Temporada 2025)")

    if st.button('🔄 Recarregar Dados'):
        st.cache_data.clear()
        st.rerun()

    df_events = load_data(API_URL_EVENTS_2025)
    if df_events.empty:
        st.warning("Nenhum dado disponível. Verifique a API.")
        return

    df_in_progress = df_events[df_events['Status'] == 'Em Andamento']
    df_scheduled = df_events[df_events['Status'] == 'Agendado']
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado')]

    if not df_in_progress.empty:
        display_games(df_in_progress, "🔴 Jogos Ao Vivo", num_cols=4)
    if not df_scheduled.empty:
        display_games(df_scheduled, "⏳ Próximos Jogos", num_cols=4)
    if not df_finalized.empty:
        display_games(df_finalized, "✅ Resultados Recentes", num_cols=4)

    # --- HISTÓRICO COMPLETO ---
    st.markdown("---")
    st.header("📜 Histórico Completo da Temporada")
    df_sorted = df_events.sort_values(by="Data", ascending=True)
    st.dataframe(df_sorted, use_container_width=True, hide_index=True)

if __name__ == '__main__':
    main()
