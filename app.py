import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
import math # Importado para o cálculo do layout em colunas

st.set_page_config(
    page_title="NFL Results Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# A URL da API é mantida
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# O mapa de logos é mantido
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "det": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "tb": "tb", "TEN": "ten",
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh", "TB": "tb", "DET": "det"
}

def get_logo_url(abbreviation):
    # Garante que a chave exista, senão usa a própria abreviação em minúsculo (útil para IDs de logo com formato diferente)
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
        detalhe_status = '' # Novo campo para o tempo do quarto

        if 'final' in status_text:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in status_text else 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
            
            # **AQUI CAPTURAMOS O TEMPO E O QUARTO PARA JOGOS AO VIVO**
            clock = status.get('displayClock', '0:00')
            period = status.get('period', 1)
            period_name = get_period_name(period)
            
            detalhe_status = f"{clock} restantes no {period_name}"
            
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        
        # fallback para descrição se não for um dos status principais
        if status_pt == 'Status Desconhecido':
            status_pt = status_type.get('description', 'Status Desconhecido')


        competitors = comp.get('competitors', [])
        home, away = (competitors + [None, None])[:2]

        home_abbr = home.get('team', {}).get('abbreviation', 'CASA') if home else "CASA"
        away_abbr = away.get('team', {}).get('abbreviation', 'FORA') if away else "FORA"
        
        # Certifica-se de que os scores são inteiros
        home_score = int(home.get('score', {}).get('value', 0)) if home and home.get('score') else 0
        away_score = int(away.get('score', {}).get('value', 0)) if away and away.get('score') else 0

        winner = home_abbr if home_score > away_score else away_abbr if away_score > home_score else "Empate"

        return {
            'Jogo': event.get('name', 'N/A'),
            'Data': data_formatada,
            'Status': status_pt,
            'Detalhe Status': detalhe_status, # Novo campo
            'Casa': home_abbr,
            'Visitante': away_abbr,
            'Vencedor': winner,
            'Score Casa': home_score,
            'Score Visitante': away_score,
        }
    except Exception as e:
        # st.error(f"Erro ao processar evento: {e}") # Descomente para debug
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
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        events = response.json().get('events', [])
        return pd.DataFrame([get_event_data(event) for event in events])
    except Exception:
        st.error("Erro ao carregar os dados da API. Verifique a URL e a conexão.")
        return pd.DataFrame()

def display_games(df, title, num_cols=4):
    st.header(title)
    
    # Divide o DataFrame em blocos de colunas
    rows = [df.iloc[i:i + num_cols] for i in range(0, len(df), num_cols)]

    for row_chunk in rows:
        # Cria as colunas para cada linha de jogos
        cols = st.columns(num_cols)
        
        for i, (index, row) in enumerate(row_chunk.iterrows()):
            with cols[i]:
                # Exibe o status principal (ex: Em Andamento)
                st.markdown(f"**{row['Status']}**", unsafe_allow_html=True)
                
                # Exibe o detalhe do status (ex: tempo restante) apenas se existir
                if row['Detalhe Status']:
                    st.markdown(f"<p style='font-size: small; color: red;'>{row['Detalhe Status']}</p>", unsafe_allow_html=True)

                # **LAYOUT DE PLACAR MELHORADO: LOGO VS PLACAR VS LOGO**
                col_home, col_score, col_away = st.columns([1, 2, 1])
                
                with col_home:
                    st.image(get_logo_url(row['Casa']), width=50)
                
                with col_score:
                    # Nomes dos times abreviados
                    st.markdown(f"**{row['Casa']}** vs **{row['Visitante']}**")
                    # Placar grande e centralizado
                    st.markdown(f"## {row['Score Casa']} - {row['Score Visitante']}")
                
                with col_away:
                    st.image(get_logo_url(row['Visitante']), width=50)

                # Informação adicional (Data/Vencedor)
                if row['Status'] == 'Agendado':
                    st.caption(f"Início: {row['Data']}")
                elif row['Status'].startswith('Finalizado'):
                    st.caption(f"Vencedor: **{row['Vencedor']}**")
                
                st.markdown("---") # Separador para cada jogo dentro da coluna


def main():
    st.title("🏈 NFL Results Dashboard")
    st.markdown("### Informações atualizadas sobre jogos da NFL (Temporada 2025)")

    # Adiciona um botão para recarregar os dados
    if st.button('🔄 Recarregar Dados'):
        st.cache_data.clear() # Limpa o cache para obter dados atualizados
        # st.rerun() # O Streamlit fará o rerun automaticamente ao rodar o main novamente

    df_events = load_data()
    if df_events.empty:
        st.warning("Nenhum dado disponível. Verifique a API.")
        return

    # Filtros mantidos
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento']
    df_scheduled = df_events[df_events['Status'] == 'Agendado']
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado')]

    # Exibe os jogos
    if not df_in_progress.empty:
        display_games(df_in_progress, "🔴 Jogos Ao Vivo", num_cols=4)
    if not df_scheduled.empty:
        display_games(df_scheduled, "⏳ Próximos Jogos", num_cols=4)
    if not df_finalized.empty:
        display_games(df_finalized, "✅ Resultados Recentes", num_cols=4)

if __name__ == '__main__':
    # Usa st.cache_data para evitar múltiplas chamadas à API desnecessárias.
    # Esta linha deve ser descomentada para rodar a aplicação real, mas como estou simulando, mantenho o load_data direto.
    # load_data = st.cache_data(load_data) 
    
    # Para demonstração em ambiente local, você pode descomentar a linha acima.
    main()
