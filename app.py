import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="NFL Results Dashboard", layout="wide", page_icon="🏈")

# --- CSS GLOBAL ---
st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #ffffff; }

.winner { color: #4CAF50; font-weight: bold; }
.loser { color: #FF4B4B; font-weight: normal; }

.score-display {
    text-align: center;
    font-size: 4.2em;
    font-weight: 900;
    margin: 0;
    line-height: 0.9;
}

.team-names {
    text-align: center;
    font-size: 1.3em;
    font-weight: 500;
    margin-bottom: 5px;
}

.status-discreto {
    font-size: 0.9em;
    color: #6c757d;
    text-align: center;
    margin-top: 5px;
    margin-bottom: 5px;
}

.game-block {
    margin-bottom: 40px;
}

/* aproxima logos do placar diretamente */
img[data-testid="stImage"] {
    margin: 0px -8px !important;
    padding: 0 !important;
}

/* força colunas internas a não criarem espaçamento */
div[data-testid="column"] {
    padding-left: 0 !important;
    padding-right: 0 !important;
}

/* tabela */
.dataframe td {
    text-align: center;
    font-size: 0.95em;
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

        if 'final' in status_text:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in status_text else 'Finalizado'
        elif status_type.get('state') == 'in':
            clock = status.get('displayClock', '0:00')
            period = status.get('period', 1)
            status_pt = f"Em Andamento – {clock} restantes no {get_period_name(period)}"
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
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

@st.cache_data(ttl=60)
def load_data(api_url):
    try:
        r = requests.get(api_url)
        r.raise_for_status()
        events = r.json().get('events', [])
        return pd.DataFrame([get_event_data(e) for e in events])
    except Exception:
        st.error("Erro ao carregar dados da API.")
        return pd.DataFrame()

def display_games(df, title, num_cols=4):
    if df.empty:
        return
    st.header(title)

    for i in range(0, len(df), num_cols):
        chunk = df.iloc[i:i + num_cols]
        chunk = chunk[(chunk['Casa'] != "ERRO") & (chunk['Visitante'] != "ERRO")]
        if chunk.empty:
            continue

        cols = st.columns(len(chunk), gap="small")

        for col, (_, row) in zip(cols, chunk.iterrows()):
            with col:
                st.markdown("<div class='game-block'>", unsafe_allow_html=True)
                casa_nome_tag = f"<span>{row['Casa']}</span>"
                visitante_nome_tag = f"<span>{row['Visitante']}</span>"
                casa_score_tag = f"<span>{row['Score Casa']}</span>"
                visitante_score_tag = f"<span>{row['Score Visitante']}</span>"

                if row['Status'].startswith('Finalizado'):
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

                st.markdown(f"<p class='team-names'>{casa_nome_tag} vs {visitante_nome_tag}</p>", unsafe_allow_html=True)

                # logos colados no placar
                col_home, col_score, col_away = st.columns([1, 1.2, 1])
                with col_home:
                    st.image(get_logo_url(row['Casa']), width=55)
                with col_score:
                    st.markdown(f"<p class='score-display'>{casa_score_tag} - {visitante_score_tag}</p>", unsafe_allow_html=True)
                with col_away:
                    st.image(get_logo_url(row['Visitante']), width=55)

                st.markdown(f"<p class='status-discreto'>{row['Status']}</p>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

def main():
    st.title("🏈 NFL Results Dashboard")
    st.markdown("### Informações atualizadas sobre jogos da NFL (Temporada 2025)")

    if st.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        st.rerun()

    df = load_data(API_URL_EVENTS_2025)
    if df.empty:
        st.warning("Nenhum dado disponível.")
        return

    df_in = df[df['Status'].str.contains('Em Andamento')]
    df_ag = df[df['Status'].str.contains('Agendado')]
    df_fin = df[df['Status'].str.startswith('Finalizado')]

    for subset, title in [(df_in, "🔴 Jogos Ao Vivo"), (df_ag, "⏳ Próximos Jogos"), (df_fin, "✅ Resultados Recentes")]:
        if not subset.empty:
            display_games(subset, title)

    st.markdown("---")
    hoje = datetime.now()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    periodo = f"{inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}"
    st.header(f"📅 Resultados da Semana Atual da NFL ({periodo})")

    df_sorted = df.sort_values(by="Data", ascending=True)

    def highlight(row):
        if row['Vencedor'] == row['Casa']:
            return ['background-color: #1b4722; color: #4CAF50'] * len(row)
        elif row['Vencedor'] == row['Visitante']:
            return ['background-color: #471b1b; color: #FF4B4B'] * len(row)
        return [''] * len(row)

    styled = df_sorted.style.apply(highlight, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
