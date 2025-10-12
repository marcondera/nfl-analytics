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
# Nota: Para usar o arquivo JSON local, você precisaria mudar a lógica de load_data()
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# Mapeamento para garantir que abreviações sejam traduzidas corretamente para a URL do logo
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin", 
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb", 
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar", 
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", 
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten", 
    "WAS": "wsh", "ARI": "ari", "ari", "WSH": "wsh"
}

def get_logo_url(abbreviation):
    """Gera a URL do logo (500x500) para melhor resolução, ajustada via HTML."""
    abbr = LOGO_MAP.get(abbreviation.upper(), abbreviation.lower())
    # URL de assets da ESPN.
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS (Corrigido para usar o nome do time no placar) ---

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
            # Detalhes de Em Andamento
            clock = status.get('displayClock', '')
            period_name = get_period_name(status.get('period', 0))
            if clock and period_name:
                detail_status = f"{clock} - {period_name}"
            elif 'shortDetail' in status_type:
                detail_status = status_type.get('shortDetail')
            
        elif status_pt == 'Finalizado' or status_pt == 'Finalizado (OT)':
            # Detalhes de Finalizado
            detail_status = status_type.get('shortDetail', 'Fim')
            
        elif status_pt == 'Agendado':
            # Detalhes de Agendado (Hora)
            dt_utc = isoparse(date_iso) 
            dt_brt = dt_utc - pd.Timedelta(hours=3)
            detail_status = dt_brt.strftime('%H:%M')
            
        
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
        
    except Exception:
        # Fallback de erro
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': 'Falha na extração',
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca e normaliza os dados da API de Events da ESPN (2025)."""
    
    # 1. Tenta carregar do arquivo local para demonstração estável
    try:
        # Busca o arquivo 'events (1).json'
        # Usamos o `fullContent` para acessar o JSON que você carregou
        data = json.loads(st.session_state.uploaded_file_data['events (1).json'])
        # st.info("Dados carregados do arquivo 'events (1).json' (Local).")
        
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        # 2. Se falhar, busca na API (mantido para o seu código principal)
        try:
            # st.info(f"Arquivo local não encontrado. Buscando na API (URL: {api_url})...")
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

# --- 3. FUNÇÃO DE RENDERIZAÇÃO CUSTOMIZADA (GRID 3x1 - Design Aprimorado) ---

def display_final_results_styled(df_finalized):
    """
    Renderiza os resultados finais em um layout de 3 cards por linha, 
    usando logos e destacando o placar vencedor.
    """
    
    rows = [row for index, row in df_finalized.iterrows()]
    
    # Custom CSS para o Dark Mode e estilo do Card
    st.markdown("""
        <style>
            /* Estilo do Card Principal */
            .nfl-card {
                background-color: #282A36; /* Fundo do Card (Dark Gray) */
                border-radius: 10px; 
                padding: 10px 8px; /* Reduzido o padding */
                margin: 5px 0; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                color: #FAFAFA;
                display: flex;
                flex-direction: column;
            }
            .nfl-date-status {
                font-size: 11px;
                color: #B0B0B0; 
                text-align: center;
                margin-bottom: 5px !important;
            }
            .nfl-team-block {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 5px;
            }
            .nfl-team-info {
                display: flex;
                align-items: center;
            }
            .nfl-score {
                font-size: 24px;
                font-weight: 500;
                color: #888888; /* Perdedor em cinza */
            }
            /* Destaque para o Vencedor */
            .nfl-score-winner {
                font-size: 24px;
                font-weight: 900; /* Negrito mais forte */
                color: #69be28; /* Verde vibrante */
            }
            .nfl-abbr {
                font-size: 10px;
                color: #B0B0B0;
                margin-left: 5px;
            }
            .nfl-footer {
                font-size: 11px;
                color: #B0B0B0;
                text-align: center;
                margin-top: 10px;
                padding-top: 5px;
                border-top: 1px solid #333;
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
                
                # Definir Status do Detalhe (melhora a exibição)
                if row['Status'] == 'Agendado':
                    status_display = f'📅 {row["Data"]} | {row["Detalhe Status"]}'
                elif row['Status'] == 'Em Andamento':
                    status_display = f'🔴 {row["Detalhe Status"]}'
                else: # Finalizado
                    status_display = f'✅ {row["Detalhe Status"]}'
                
                
                # --- START CARD ---
                st.markdown('<div class="nfl-card">', unsafe_allow_html=True)

                # 1. Data/Status
                st.markdown(f'<p class="nfl-date-status">{status_display}</p>', unsafe_allow_html=True)

                # 2. Time Visitante
                away_score_class = "nfl-score-winner" if is_away_winner else "nfl-score"
                st.markdown(
                    f"""
                    <div class="nfl-team-block">
                        <div class="nfl-team-info">
                            <img src="{get_logo_url(row['Visitante'])}" width="30" height="30" style="margin-right: 5px;">
                            <span class="nfl-abbr">{row['Visitante']}</span>
                        </div>
                        <span class="{away_score_class}">{row["Score Visitante"]}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                # 3. Time Casa
                home_score_class = "nfl-score-winner" if is_home_winner else "nfl-score"
                st.markdown(
                    f"""
                    <div class="nfl-team-block">
                        <div class="nfl-team-info">
                            <img src="{get_logo_url(row['Casa'])}" width="30" height="30" style="margin-right: 5px;">
                            <span class="nfl-abbr">{row['Casa']}</span>
                        </div>
                        <span class="{home_score_class}">{row["Score Casa"]}</span>
                    </div>
                    """, unsafe_allow_html=True
                )
                
                # 4. Status Vencedor (Rodapé) - Simplificado
                footer_text = row["Detalhe Status"] if row['Status'] != 'Finalizado' else f'Vencedor: {row["Vencedor"]}'
                
                st.markdown(f'<p class="nfl-footer">{footer_text}</p>', unsafe_allow_html=True)
                
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
    
    # Remove a URL de loading e a mensagem desnecessária
    st.title(f"🏈 Dashboard {league_name} - {current_season}")
    st.markdown("---")
    
    # --- Side Bar e Controles (Se for o caso) ---
    st.sidebar.header("Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
    st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
    st.sidebar.markdown("---")
    
    # Salva o JSON no estado da sessão para ser acessado por load_data
    if "uploaded_file_data" not in st.session_state:
        st.session_state["uploaded_file_data"] = {}

    try:
        # Prepara o JSON para o load_data usar
        with open("events (1).json", "r") as f:
             st.session_state["uploaded_file_data"]["events (1).json"] = f.read()
    except FileNotFoundError:
        # st.warning("Arquivo 'events (1).json' não encontrado na estrutura do projeto.")
        pass

    
    # --- CARREGAMENTO DE DADOS ---
    # É importante carregar os dados antes das métricas
    df_events = load_data() 

    if df_events.empty:
        st.warning("Não foi possível carregar os dados. Verifique a API ou o arquivo JSON.")
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
    
    # 1. Jogos em Andamento (Ao Vivo)
    st.header("🔴 Jogos Ao Vivo (Em Andamento)")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Data', ascending=False)
    
    if not df_in_progress.empty:
        display_final_results_styled(df_in_progress)
    else:
        st.info("Nenhum jogo em andamento no momento.")

    st.markdown("---")

    # 2. Resultados Recentes (Finalizados)
    st.header("✅ Resultados Finais")
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        display_final_results_styled(df_finalized)
    else:
        st.info("Nenhum resultado finalizado encontrado.")


if __name__ == '__main__':
    main()
