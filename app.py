import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests
from dateutil.parser import isoparse

# Configuração da página
st.set_page_config(
    page_title="NFL Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 1. CONFIGURAÇÃO DE LOGOS E API ---

API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "det": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "tb": "tb", "TEN": "ten",
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh", "TB": "tb", "DET": "det"
}

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(abbreviation.upper(), abbreviation.lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

# --- 2. FUNÇÕES DE PROCESSAMENTO DE DADOS ---

def get_period_name(period):
    if period == 1: return "1º Quarto"
    if period == 2: return "2º Quarto"
    if period == 3: return "3º Quarto"
    if period == 4: return "4º Quarto"
    if period > 4: return "Prorrogação"
    return ""

def get_event_data(event):
    data_formatada = "N/A"
    status_pt = "N/A"
    winner_team_abbr = "A definir"
    detail_status = "N/A"
    home_team_abbr = "N/A"
    away_team_abbr = "N/A"

    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')

        if date_iso:
            try:
                dt_utc = isoparse(date_iso)
                dt_brt = dt_utc - pd.Timedelta(hours=3)
                data_formatada = dt_brt.strftime('%d/%m/%Y')
            except Exception:
                pass

        status = comp.get('status', {})
        status_type = status.get('type', {})

        status_text_check = str(status_type).lower()

        if 'final' in status_text_check:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in status_text_check or 'overtime' in status_text_check else 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
            status_pt = status_type.get('description', 'Status Desconhecido')

        detail_status = status.get('detail', status_type.get('shortDetail', 'N/A'))

        if status_pt == 'Em Andamento':
            clock = status.get('displayClock', '')
            period_name = get_period_name(status.get('period', 0))
            if clock and period_name:
                detail_status = f"{period_name} - {clock}"
            else:
                detail_status = status_type.get('shortDetail', 'Ao Vivo')

        elif status_pt == 'Finalizado' or status_pt == 'Finalizado (Prorrogação)':
            detail_status = status_type.get('shortDetail', 'Final')

        elif status_pt == 'Agendado':
            dt_utc = isoparse(date_iso)
            dt_brt = dt_utc - pd.Timedelta(hours=3)
            detail_status = dt_brt.strftime('%H:%M BRT')

        competitors = comp.get('competitors', [])
        home_team = {}
        away_team = {}

        if len(competitors) >= 2:
            c1 = competitors[0]
            c2 = competitors[1]

            if c1.get('homeAway') == 'home':
                home_team, away_team = c1, c2
            elif c2.get('homeAway') == 'home':
                home_team, away_team = c2, c1
            else:
                home_team, away_team = c1, c2

        home_score = int(home_team.get('score', {}).get('value', 0.0))
        away_score = int(away_team.get('score', {}).get('value', 0.0))

        home_team_abbr = home_team.get('team', {}).get('abbreviation', 'CASA')
        away_team_abbr = away_team.get('team', {}).get('abbreviation', 'FORA')

        if status_pt.startswith('Finalizado'):
            if home_score > away_score:
                winner_team_abbr = home_team_abbr
            elif away_score > home_score:
                winner_team_abbr = away_team_abbr
            else:
                winner_team_abbr = "Empate"

        return {
            'Jogo': event.get('name', 'N/A'),
            'Data': data_formatada,
            'Status': status_pt,
            'Casa': home_team_abbr,
            'Visitante': away_team_abbr,
            'Vencedor': winner_team_abbr,
            'Score Casa': home_score,
            'Score Visitante': away_score,
            'Detalhe Status': detail_status,
        }

    except Exception as e:
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': 'Falha na extração',
        }

def load_data(api_url=API_URL_EVENTS_2025):
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar dados da API. Verifique a URL ou a conexão de rede: {e}")
        return pd.DataFrame()
    except json.JSONDecodeError as e:
        st.error(f"Erro ao decodificar JSON da API: {e}")
        return pd.DataFrame()

    events_list = data.get('events', [])
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None and item['Status'] != 'ERRO']

    if not events_data:
        st.warning("A API retornou dados, mas a lista de eventos está vazia ou todos os eventos falharam na extração.")
        return pd.DataFrame()

    df = pd.DataFrame(events_data)
    return df

# --- 3. FUNÇÕES DE RENDERIZAÇÃO ---

def highlight_winner(team, winner, score, is_draw):
    if is_draw:
        return f"**{team}** (Empate) — **{score}**"
    elif team == winner:
        return f":green[**{team}**] — :green[**{score}**]"
    else:
        return f"{team} — {score}"

def display_games(df):
    for idx, row in df.iterrows():
        st.subheader(f"{row['Jogo']}")
        is_draw = row['Vencedor'] == 'Empate'
        col1, col2 = st.columns(2)
        with col1:
            st.write(highlight_winner(row['Casa'], row['Vencedor'], row['Score Casa'] if row['Status'] != 'Agendado' else '-', is_draw), unsafe_allow_html=True)
            st.image(get_logo_url(row['Casa']), width=50)
        with col2:
            st.write(highlight_winner(row['Visitante'], row['Vencedor'], row['Score Visitante'] if row['Status'] != 'Agendado' else '-', is_draw), unsafe_allow_html=True)
            st.image(get_logo_url(row['Visitante']), width=50)
        st.write(f"Status: {row['Status']} | Detalhe: {row['Detalhe Status']}")
        if row['Status'].startswith("Finalizado"):
            if is_draw:
                st.info("Empate!")
            else:
                st.info(f":green[Vencedor: **{row['Vencedor']}**]")
        st.write("---")

def display_season_history_table(df_history):
    def color_winner(val, winner, empate):
        if empate or pd.isna(val):
            return ''
        return 'color: green; font-weight:bold' if val == winner else ''
    df_table = df_history[
        ['Data', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante', 'Vencedor', 'Detalhe Status', 'Jogo']
    ].rename(columns={
        'Score Casa': 'Placar Casa',
        'Score Visitante': 'Placar Fora',
        'Detalhe Status': 'Status',
        'Visitante': 'Time Visitante',
        'Casa': 'Time Casa'
    })
    # Aplica destaque na coluna do vencedor e nos placares
    styled_df = df_table.style.apply(
        lambda row: [
            color_winner(row['Time Casa'], row['Vencedor'], row['Vencedor']=='Empate'),
            '',  # Placar Casa
            '',  # Data
            color_winner(row['Time Visitante'], row['Vencedor'], row['Vencedor']=='Empate'),
            '',  # Placar Fora
            'color: green; font-weight:bold' if row['Vencedor'] not in ['N/A', 'Empate'] else '',
            '',  # Status
            ''   # Jogo
        ], axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    st.title("🏈 Resultados da NFL")

    df_events = load_data()

    if df_events.empty:
        st.error("Não foi possível carregar os dados. O dashboard não será exibido. Por favor, verifique as mensagens de erro acima.")
        return

    # --- JOGOS AO VIVO (EM ANDAMENTO) ---
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Data', ascending=False)
    df_scheduled = df_events[
        df_events['Status'] == 'Agendado'
    ].sort_values(by='Data', ascending=True)
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)

    if not df_in_progress.empty:
        st.header("🔴 Ao Vivo")
        display_games(df_in_progress)
        st.header("⏳ Próximos Jogos")
        if not df_scheduled.empty:
            display_games(df_scheduled)
        else:
            st.info("Nenhum jogo agendado nos dados fornecidos.")
    else:
        st.header("⏳ Próximos Jogos")
        if not df_scheduled.empty:
            display_games(df_scheduled)
        else:
            st.info("Nenhum jogo agendado nos dados fornecidos.")
        st.header("✅ Resultados Recentes")
        if not df_finalized.empty:
            display_games(df_finalized.head(9))
        else:
            st.info("Nenhum resultado finalizado encontrado.")

    # --- HISTÓRICO COMPLETO DA TEMPORADA (TABELA) ---
    st.header("📚 Histórico Completo da Temporada")
    if not df_finalized.empty:
        display_season_history_table(df_finalized)
    else:
        st.info("Nenhum resultado finalizado no histórico para exibir.")

if __name__ == '__main__':
    main()