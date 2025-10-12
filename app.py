import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 

# Configuração da página (Garante que o tema do Streamlit será dark mode e layout wide)
st.set_page_config(
    page_title="NFL 2025 Eventos e Resultados",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. CONFIGURAÇÃO DE LOGOS E API ---
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# Mapeamento para garantir que abreviações sejam traduzidas corretamente para a URL do logo
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin", 
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb", 
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar", 
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", 
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten", 
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh"
}

def get_logo_url(abbreviation):
    """Gera a URL do logo (50x50) baseado na abreviação do time."""
    abbr = LOGO_MAP.get(abbreviation.upper(), abbreviation.lower())
    # URL de assets da ESPN.
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS (Mantidas) ---

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
    """Extrai e formata os dados principais de um único evento."""
    # (Conteúdo da função get_event_data é mantido inalterado da versão anterior)
    
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
        
        if status_pt == 'Em Andamento' and ('N/A' in detail_status or not detail_status):
            clock = status.get('displayClock', '')
            period_name = get_period_name(status.get('period', 0))
            detail_status = f"{clock} - {period_name}" if clock and period_name else status_type.get('shortDetail', 'Em Andamento')
        
        competitors = comp.get('competitors', [])
        home_team = {} 
        away_team = {} 

        if len(competitors) >= 2:
            c1 = competitors[0]
            c2 = competitors[1]
            
            c1 = c1 if isinstance(c1, dict) else {}
            c2 = c2 if isinstance(c2, dict) else {}

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
        
    except Exception:
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': 'Falha na extração',
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca e normaliza os dados da API de Events da ESPN (2025)."""
    
    st.info(f"Buscando eventos da NFL 2025 (URL: {api_url})...")
    
    try:
        response = requests.get(api_url)
        response.raise_for_status() 
        data = response.json()
        
    except requests.exceptions.RequestException:
        st.error(f"Erro ao buscar dados da API. Verifique a URL e autenticação.")
        return pd.DataFrame()
    except json.JSONDecodeError:
        st.error("Erro ao decodificar a resposta como JSON.")
        return pd.DataFrame()

    events_list = data.get('events', [])
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    if not events_data:
        return pd.DataFrame()
        
    df = pd.DataFrame(events_data)
    return df

# --- 3. FUNÇÃO DE RENDERIZAÇÃO CUSTOMIZADA (GRID 3x1) ---

def display_final_results_styled(df_finalized):
    """
    Renderiza os resultados finais em um layout de 3 cards por linha, 
    usando logos e destacando o vencedor (Compacto e Elegante).
    """
    
    rows = [row for index, row in df_finalized.iterrows()]
    
    # Custom CSS para o Dark Mode e estilo do Card
    st.markdown("""
        <style>
            /* Estilo do Card Principal */
            .nfl-card {
                background-color: #282A36; /* Fundo do Card (Dark Gray) */
                border-radius: 10px; 
                padding: 15px; 
                margin: 5px 0; 
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
                color: #FAFAFA; /* Cor principal do texto */
            }
            .nfl-card p {
                margin: 0;
            }
            .nfl-date {
                font-size: 11px;
                color: #B0B0B0; /* Cor secundária (Data/Status) */
                text-align: center;
                margin-bottom: 10px !important;
            }
            .nfl-score {
                font-size: 28px;
                font-weight: 500;
                color: #FAFAFA; /* Placar normal */
            }
            /* Destaque para o Vencedor */
            .nfl-score-winner {
                font-weight: 900;
                color: #69be28; /* Green (Similar ao Google) */
            }
            .nfl-vs {
                font-size: 14px;
                color: #888;
                font-weight: bold;
                margin-top: 10px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Processa em grupos de 3 para o layout de colunas
    for i in range(0, len(rows), 3):
        
        cols = st.columns(3)
        chunk = rows[i:i+3]
        
        for j, row in enumerate(chunk):
            with cols[j]:
                
                is_home_winner = row['Vencedor'] == row['Casa']
                is_away_winner = row['Vencedor'] == row['Visitante']
                
                # --- START CARD ---
                st.markdown('<div class="nfl-card">', unsafe_allow_html=True)

                # 1. Data/Status
                st.markdown(f'<p class="nfl-date">{row["Data"]} | {row["Detalhe Status"]}</p>', unsafe_allow_html=True)

                # 2. Layout do Placar: Logo | Score | VS | Score | Logo
                # Configuração de colunas: (Logo, Score, VS, Score, Logo)
                col_away_logo, col_away_score, col_vs, col_home_score, col_home_logo = st.columns([1.5, 2, 1, 2, 1.5])
                
                # --- TIME VISITANTE ---
                with col_away_logo:
                    # O Streamlit ajusta a imagem automaticamente
                    st.image(get_logo_url(row['Visitante']), width=35)
                with col_away_score:
                    score_class = "nfl-score-winner" if is_away_winner else "nfl-score"
                    # Injeta o score com a classe CSS correta
                    st.markdown(f'<p style="text-align: right;"><span class="{score_class}">{row["Score Visitante"]}</span></p>', unsafe_allow_html=True)

                # --- SEPARADOR VS ---
                with col_vs:
                    st.markdown('<p class="nfl-vs" style="text-align: center;">VS</p>', unsafe_allow_html=True)
                    
                # --- TIME CASA ---
                with col_home_score:
                    score_class = "nfl-score-winner" if is_home_winner else "nfl-score"
                    st.markdown(f'<p style="text-align: left;"><span class="{score_class}">{row["Score Casa"]}</span></p>', unsafe_allow_html=True)
                with col_home_logo:
                    st.image(get_logo_url(row['Casa']), width=35)
                
                # 3. Status Vencedor (Rodapé)
                winner_text = f'<b style="color: #69be28;">{row["Vencedor"]}</b>' if row['Vencedor'] not in ['Empate', 'A definir'] else row["Vencedor"]
                st.markdown(f'<p style="font-size: 10px; color: #AAA; margin-top: 10px; text-align: center; border-top: 1px solid #333; padding-top: 8px;">Vencedor: {winner_text}</p>', unsafe_allow_html=True)
                
                # --- END CARD ---
                st.markdown('</div>', unsafe_allow_html=True)
                
# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    # Injeta CSS principal para o fundo global e headers em Dark Mode
    st.markdown("""
        <style>
            .stApp {
                background-color: #0E1117; /* Fundo principal do app */
            }
            h1, h2, h3, h4, h5, h6 {
                color: #FAFAFA; /* Títulos em branco */
            }
        </style>
    """, unsafe_allow_html=True)
    
    league_name, current_season = get_league_metadata()
    
    st.title(f"🏈 Dashboard {league_name} - {current_season}")
    st.markdown("---")
    
    st.sidebar.header("Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
    st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
    st.sidebar.markdown("---")
    
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
    
    # --- JOGOS AO VIVO E RESULTADOS FINAIS ---
    
    # 1. Jogos em Andamento (Ao Vivo) - Usando o novo estilo de Card para consistência
    st.header("🔴 Jogos Ao Vivo (Em Andamento)")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        display_final_results_styled(df_in_progress)
    else:
        st.info("Nenhum jogo em andamento no momento.")

    st.markdown("---")

    # 2. Resultados Recentes (Finalizados) - NOVO VISUAL CUSTOMIZADO
    st.header("✅ Resultados Finais")
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        # Chama a função que renderiza os cards visuais 3x1
        display_final_results_styled(df_finalized)
    else:
        st.info("Nenhum resultado finalizado encontrado.")


if __name__ == '__main__':
    main()
