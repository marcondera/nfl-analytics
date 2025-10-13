import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
import math

# **NOVIDADE: FORÇANDO O DARK MODE**
st.set_page_config(
    page_title="NFL Results Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
    # Configurações para forçar o tema escuro
    page_icon="🏈"
)

# Adiciona estilos customizados para forçar o dark mode e destacar o placar
st.markdown("""
<style>
    /* Força o tema escuro no Streamlit, garantindo consistência */
    .stApp {
        background-color: #0e1117; 
        color: #ffffff;
    }
    /* Estilo para destacar o texto do vencedor em verde */
    .winner {
        color: #4CAF50; /* Verde */
        font-weight: bold;
    }
    /* Alinhamento e tamanho do placar */
    .score-display {
        text-align: center;
        font-size: 2.5em; /* Maior placar */
        font-weight: bold;
        margin: 5px 0;
    }
    /* Alinhamento dos times */
    .team-names {
        text-align: center;
        font-size: 1.1em;
        font-weight: 500;
        margin-bottom: 5px;
    }
    /* Estilo para o detalhe do status 'Ao Vivo' */
    .live-detail {
        font-size: small;
        color: #FF4B4B; /* Cor vermelha para indicar 'Ao Vivo' */
        text-align: center;
        margin-top: -10px;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)


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

def load_data(api_url=API_URL_EVENTS_2025):
    # Uso st.cache_data internamente para gerenciar o cache da API
    @st.cache_data(ttl=60) # Cache por 60 segundos
    def fetch_data(url):
        try:
            response = requests.get(url)
            response.raise_for_status()
            events = response.json().get('events', [])
            return pd.DataFrame([get_event_data(event) for event in events])
        except Exception:
            st.error("Erro ao carregar os dados da API. Verifique a URL e a conexão.")
            return pd.DataFrame()

    return fetch_data(api_url)

def display_games(df, title, num_cols=4):
    st.header(title)
    
    rows = [df.iloc[i:i + num_cols] for i in range(0, len(df), num_cols)]

    for row_chunk in rows:
        cols = st.columns(num_cols)
        
        for i, (index, row) in enumerate(row_chunk.iterrows()):
            with cols[i]:
                # Exibe o status principal
                st.markdown(f"<p class='team-names'>**{row['Status']}**</p>", unsafe_allow_html=True)
                
                # Exibe o detalhe do status para jogos ao vivo
                if row['Detalhe Status']:
                    st.markdown(f"<p class='live-detail'>{row['Detalhe Status']}</p>", unsafe_allow_html=True)
                
                # Prepara o nome e placar dos times com formatação
                casa_nome = row['Casa']
                visitante_nome = row['Visitante']
                casa_score = str(row['Score Casa'])
                visitante_score = str(row['Score Visitante'])
                
                # **LÓGICA PARA APLICAR VERDE E NEGRITO NO VENCEDOR**
                if row['Status'].startswith('Finalizado'):
                    if row['Vencedor'] == casa_nome:
                        casa_nome = f"<span class='winner'>{casa_nome}</span>"
                        casa_score = f"<span class='winner'>{casa_score}</span>"
                    elif row['Vencedor'] == visitante_nome:
                        visitante_nome = f"<span class='winner'>{visitante_nome}</span>"
                        visitante_score = f"<span class='winner'>{visitante_score}</span>"


                # Exibição dos Nomes (separado para controle)
                st.markdown(f"<p class='team-names'>{casa_nome} vs {visitante_nome}</p>", unsafe_allow_html=True)

                # Layout para Logos e Placar
                col_home, col_score, col_away = st.columns([1, 2, 1])
                
                with col_home:
                    st.image(get_logo_url(row['Casa']), width=50)
                
                with col_score:
                    # Exibição do Placar com a formatação CSS 'score-display'
                    st.markdown(f"<p class='score-display'>{casa_score} - {visitante_score}</p>", unsafe_allow_html=True)
                
                with col_away:
                    st.image(get_logo_url(row['Visitante']), width=50)

                # Informação adicional (Data)
                if row['Status'] == 'Agendado':
                    st.caption(f"Início: {row['Data']}")
                
                st.markdown("---") # Separador para cada jogo dentro da coluna


def main():
    st.title("🏈 NFL Results Dashboard")
    st.markdown("### Informações atualizadas sobre jogos da NFL (Temporada 2025)")

    # Adiciona um botão para recarregar os dados, que limpa o cache
    if st.button('🔄 Recarregar Dados'):
        st.cache_data.clear()
        st.rerun()

    df_events = load_data()
    if df_events.empty:
        st.warning("Nenhum dado disponível. Verifique a API.")
        return

    df_in_progress = df_events[df_events['Status'] == 'Em Andamento']
    df_scheduled = df_events[df_events['Status'] == 'Agendado']
    # O filtro de Finalizado foi simplificado, já que não precisamos do texto 'Vencedor'
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado')] 

    if not df_in_progress.empty:
        display_games(df_in_progress, "🔴 Jogos Ao Vivo", num_cols=4)
    if not df_scheduled.empty:
        display_games(df_scheduled, "⏳ Próximos Jogos", num_cols=4)
    if not df_finalized.empty:
        display_games(df_finalized, "✅ Resultados Recentes", num_cols=4)

if __name__ == '__main__':
    main()
