import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 

# Configuração da página
st.set_page_config(
    page_title="NFL Dashboard",
    layout="wide", # Essencial para que a largura funcione
    initial_sidebar_state="collapsed" 
)

# --- CORREÇÃO DE LAYOUT CSS ESTÁVEL ---
# Força a centralização e largura máxima, o que evita o bug constante do Streamlit.
st.markdown("""
<style>
/* Centraliza o bloco principal do aplicativo e define a largura MÁXIMA */
div[data-testid="stVerticalBlock"] {
    width: 100%;
    max-width: 1000px; /* Largura máxima desejada para centralizar o conteúdo */
    margin: 0 auto; /* Força a centralização horizontal */
}

/* Remove o padding lateral do container principal para usar a largura total de 1000px */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    padding-left: 0rem;
    padding-right: 0rem;
}

.result-card {
    border: 1px solid #ddd;
    padding: 15px;
    margin-bottom: 10px;
    border-radius: 8px;
    background-color: #f9f9f9;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
}
.home-team, .away-team {
    font-weight: bold;
}
.score {
    font-size: 1.2em;
    font-weight: bold;
}
.game-info {
    font-size: 0.9em;
    color: #555;
}
</style>
""", unsafe_allow_html=True)
# -------------------------------------------------------------


# --- 1. CONFIGURAÇÃO DE LOGOS E API ---

# VOLTAMOS À URL ORIGINAL DA API
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# Mapeamento para garantir que abreviações sejam traduzidas corretamente para a URL do logo
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin", 
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "det": "det", "GB": "gb", 
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar", 
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", 
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten", 
    "WAS": "was", "ARI": "ari", "WSH": "wsh", "DET": "det"
}

def get_logo_url(team_abbr):
    """Gera a URL do logo da equipe a partir da abreviação."""
    base_url = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/"
    slug = LOGO_MAP.get(team_abbr.upper(), 'nfl')
    return f"{base_url}{slug}.png&h=40&w=40"


# --- 2. FUNÇÕES AUXILIARES DE PROCESSAMENTO DE DADOS (Inalteradas) ---

def get_league_metadata():
    """Retorna informações estáticas da liga."""
    return 'NFL', '2025'

def get_period_name(period):
    """Mapeia o número do período para o nome do Quarto/Overtime."""
    if period == 1: return "1º Quarto"
    if period == 2: return "2º Quarto"
    if period == 3: return "3º Quarto"
    if period == 4: return "4º Quarto"
    if period > 4: return "Prorrogação"
    return ""

def get_event_data(event):
    """
    Extrai e formata os dados principais de um único evento.
    (Lógica mantida como no seu arquivo)
    """
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
            status_pt = 'Finalizado (OT)' if 'ot' in status_text_check or 'overtime' in status_text_check else 'Finalizado'
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

        elif status_pt == 'Finalizado' or status_pt == 'Finalizado (OT)':
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

        try:
            home_score = int(home_team.get('score', {}).get('value', 0.0))
        except (TypeError, ValueError):
            home_score = 0
            
        try:
            away_score = int(away_team.get('score', {}).get('value', 0.0))
        except (TypeError, ValueError):
            away_score = 0

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
            'Detalhe Status': f'Falha na extração: {type(e).__name__}',
        }

def load_data(api_url=API_URL_EVENTS_2025):
    """
    Busca e normaliza os dados da API de Events da ESPN (2025)
    **USANDO REQUISIÇÃO REAL À API.**
    """
    
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
    events_data = [item for item in events_data if item is not None and item['Status'] != 'ERRO']
        
    df = pd.DataFrame(events_data)
    return df

# --- FUNÇÃO DE ESTILIZAÇÃO (CARDS) ---

def display_final_results_styled(df_results):
    """Exibe resultados em um formato de card estilizado com HTML/CSS e colunas."""
    
    # Define o número de colunas (3 cards por linha)
    cols = st.columns(3)

    for i, row in df_results.iterrows():
        col = cols[i % 3] 
        
        home_logo_url = get_logo_url(row['Casa'])
        away_logo_url = get_logo_url(row['Visitante'])
        
        status_text = row['Detalhe Status']
        if row['Status'].startswith('Finalizado'):
            status_style = 'color: #1a9953; font-weight: bold;'
        elif row['Status'] == 'Agendado':
             status_style = 'color: #ff9900; font-weight: bold;'
        else:
            status_style = 'color: #007bff; font-weight: bold;'

        # Monta o HTML do card
        card_html = f"""
        <div class="result-card">
            <div style="text-align: center; margin-bottom: 10px; {status_style}">
                {status_text}
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <div class="home-team" style="display: flex; align-items: center;">
                    <img src="{home_logo_url}" style="margin-right: 5px; height: 30px; width: 30px;"/>
                    {row['Casa']} 
                </div>
                <div class="score">{row['Score Casa']}</div>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="away-team" style="display: flex; align-items: center;">
                    <img src="{away_logo_url}" style="margin-right: 5px; height: 30px; width: 30px;"/>
                    {row['Visitante']} 
                </div>
                <div class="score">{row['Score Visitante']}</div>
            </div>
            
            <div class="game-info" style="text-align: center; margin-top: 10px;">
                Jogo: {row['Data']}
            </div>
        </div>
        """
        
        col.markdown(card_html, unsafe_allow_html=True)


# --- 3. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    league_name, current_season = get_league_metadata()
    
    # --- DEFINIÇÕES DA SIDEBAR ---
    st.sidebar.header("Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
    st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Recarregar Dados Agora"):
        st.rerun() 
    # -----------------------------

    # O CONTEÚDO AGORA ESTÁ DIRETAMENTE NA PÁGINA COM CENTRALIZAÇÃO POR CSS
    st.title(f"🏈 Dashboard {league_name} - {current_season}")
    st.markdown("---")
        
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
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Jogos", total_games)
    col2.metric("Finalizados", finalizados)
    col3.metric("Em Andamento", em_andamento)
    col4.metric("Agendados", agendados)

    st.markdown("---")
    
    # --- JOGOS EM ANDAMENTO ---
    st.header("▶️ Jogos ao Vivo")
    df_in_progress = df_events[
        df_events['Status'] == 'Em Andamento'
    ].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        display_final_results_styled(df_in_progress.head(3))
    else:
        st.markdown('<p style="color:#888; text-align: center; margin-bottom: 1rem;">Nenhum jogo em andamento no momento.</p>', unsafe_allow_html=True)

    st.markdown("---")
    
    # --- RESULTADOS RECENTES (CARDS) ---
    st.header("✅ Resultados Recentes")
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)

    if not df_finalized.empty:
        display_final_results_styled(df_finalized.head(6))
    else:
        st.markdown('<p style="color:#888; text-align: center; margin-bottom: 1rem;">Nenhum resultado finalizado encontrado.</p>', unsafe_allow_html=True)

    # SEPARADOR ENTRE RESULTADOS RECENTES E AGENDADOS
    st.markdown("---")

    # --- JOGOS AGENDADOS ---
    st.header("⏳ Próximos Jogos")
    df_scheduled = df_events[
        df_events['Status'] == 'Agendado'
    ].sort_values(by='Data', ascending=True)

    if not df_scheduled.empty:
        display_final_results_styled(df_scheduled.head(6))
    else:
        st.markdown('<p style="color:#888; text-align: center; margin-bottom: 1rem;">Nenhum jogo agendado nos dados fornecidos.</p>', unsafe_allow_html=True)

    # SEPARADOR ENTRE AGENDADOS E HISTÓRICO COMPLETO
    st.markdown("---")

    # --- HISTÓRICO COMPLETO DA TEMPORADA (TABELA) ---
    st.header("📚 Histórico Completo da Temporada")
    st.dataframe(
        df_events[['Data', 'Status', 'Jogo', 'Vencedor', 'Score Casa', 'Score Visitante', 'Detalhe Status']],
        use_container_width=True
    )


if __name__ == '__main__':
    main()
