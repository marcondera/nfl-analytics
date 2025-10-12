import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 

# Configuração da página (Estilo Dark Mode aprimorado)
st.set_page_config(
    page_title="NFL 2025 Eventos e Resultados",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. CONFIGURAÇÃO DA API (LINK ESTÁVEL) ---
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# --- Mapeamento de Logos (Abreviações para URL do Asset da ESPN) ---
# Usamos um mapeamento para garantir que abreviações como "LV" (Raiders) funcionem no caminho do asset.
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
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS (Inalteradas) ---

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
    """
    Extrai e formata os dados principais de um único evento, incluindo cores dos times.
    (Função mantida para funcionalidade, mesmo que a cor não seja usada no visual final do card)
    """
    
    data_formatada = "N/A"
    hora_formatada = "N/A"
    status_pt = "N/A"
    winner_team_abbr = "A definir"
    detail_status = "N/A" 
    home_team_abbr = "N/A"
    away_team_abbr = "N/A"
    home_team_color = "000000" 
    away_team_color = "000000"
    
    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')

        # --- CORREÇÃO DE DATA/HORA ---
        if date_iso:
            try:
                dt_utc = isoparse(date_iso) 
                dt_brt = dt_utc - pd.Timedelta(hours=3) # Converte para BRT (UTC-3)

                data_formatada = dt_brt.strftime('%d/%m/%Y')
                hora_formatada = dt_brt.strftime('%H:%M') + ' BRT'
            except Exception:
                pass 
        # --- FIM DA CORREÇÃO DE DATA/HORA ---

        # Extração do Status Principal
        status = comp.get('status', {}) 
        status_type = status.get('type', {})
        
        # --- FIX ROBUSTO DE STATUS ---
        status_text_check = str(status_type).lower() 

        if 'final' in status_text_check:
            if 'ot' in status_text_check or 'overtime' in status_text_check:
                status_pt = 'Finalizado (OT)'
            else:
                status_pt = 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
            status_pt = status_type.get('description', 'Status Desconhecido') 
        # --- FIM FIX ROBUSTO DE STATUS ---

        
        detail_status = status.get('detail', status_type.get('shortDetail', 'N/A'))
        
        # --- LÓGICA DE CONSTRUÇÃO DO DETALHE STATUS ---
        if status_pt == 'Em Andamento' and ('N/A' in detail_status or not detail_status):
            clock = status.get('displayClock', '')
            period_num = status.get('period', 0)
            period_name = get_period_name(period_num)
            
            if clock and period_name:
                detail_status = f"{clock} - {period_name}"
            elif status_type.get('shortDetail'):
                detail_status = status_type.get('shortDetail', 'Em Andamento')
        
        # 2. Extração dos times e scores
        competitors = comp.get('competitors', [])
        home_team = {} 
        away_team = {} 

        if len(competitors) >= 2:
            c1 = competitors[0]
            c2 = competitors[1]
            
            c1 = c1 if isinstance(c1, dict) else {}
            c2 = c2 if isinstance(c2, dict) else {}

            if c1.get('homeAway') == 'home':
                home_team = c1
                away_team = c2
            elif c2.get('homeAway') == 'home':
                home_team = c2
                away_team = c1
            else:
                home_team = c1
                away_team = c2
                
        # Extração de Scores e Nomes
        home_score = int(home_team.get('score', {}).get('value', 0.0))
        away_score = int(away_team.get('score', {}).get('value', 0.0))
        
        home_team_abbr = home_team.get('team', {}).get('abbreviation', 'CASA')
        away_team_abbr = away_team.get('team', {}).get('abbreviation', 'FORA')
        
        # Extração das Cores
        home_team_color = home_team.get('team', {}).get('color', home_team_color)
        away_team_color = away_team.get('team', {}).get('color', away_team_color)
            
        # Determinação do Vencedor
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
            'Hora': hora_formatada,
            'Status': status_pt, 
            'Casa': home_team_abbr,
            'Visitante': away_team_abbr,
            'Vencedor': winner_team_abbr,
            'Score Casa': home_score,
            'Score Visitante': away_score,
            'Detalhe Status': detail_status,
            'Home Color': home_team_color,
            'Away Color': away_team_color
        }
        
    except Exception as e:
        # Fallback de erro
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A', 'Hora': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': f'Falha na extração',
            'Home Color': '333333', 'Away Color': '333333'
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca e normaliza os dados da API de Events da ESPN (2025)."""
    
    # st.info(f"Buscando eventos da NFL 2025 (URL: {api_url})...")
    
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
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    if not events_data:
        # st.warning("Não foi possível extrair dados válidos dos eventos após o processamento.")
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
    
    # Processa em grupos de 3 para o layout de colunas
    for i in range(0, len(rows), 3):
        
        # Cria 3 colunas para o layout em grade
        cols = st.columns(3)
        chunk = rows[i:i+3]
        
        for j, row in enumerate(chunk):
            with cols[j]:
                
                is_home_winner = row['Vencedor'] == row['Casa']
                is_away_winner = row['Vencedor'] == row['Visitante']
                
                # O Card principal
                st.markdown(
                    f"""
                    <div style="
                        border: 1px solid #333; 
                        border-radius: 10px; 
                        padding: 15px 10px; 
                        margin: 5px 0; 
                        background-color: #1E1E1E; 
                        box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
                    ">
                    """, unsafe_allow_html=True
                )
                
                # Título: Data e Status
                st.markdown(f'<p style="font-size: 11px; color: #AAA; margin: 0 0 10px 0; text-align: center;">{row["Data"]} | {row["Detalhe Status"]}</p>', unsafe_allow_html=True)

                # --- Layout Interno do Placar (Casa vs Visitante) ---
                col_score_away, col_score_home = st.columns(2)
                
                # --- Time Visitante ---
                with col_score_away:
                    away_score_weight = "900" if is_away_winner else "normal" # Negrito mais forte
                    away_score_color = "#FAFAFA" if is_away_winner else "#888888" # Corrigido para branco/cinza no fundo escuro

                    st.markdown(
                        f"""
                        <div style="text-align: center; line-height: 1;">
                            <img src="{get_logo_url(row['Visitante'])}" width="35">
                            <p style="font-size: 22px; margin: 5px 0 0px 0; font-weight: {away_score_weight}; color: {away_score_color};">
                                {row['Score Visitante']}
                            </p>
                            <p style="font-size: 11px; color: #AAA; margin: 0; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">{row['Visitante']}</p>
                        </div>
                        """, unsafe_allow_html=True
                    )
                
                # --- Time Casa ---
                with col_score_home:
                    home_score_weight = "900" if is_home_winner else "normal"
                    home_score_color = "#FAFAFA" if is_home_winner else "#888888"

                    st.markdown(
                        f"""
                        <div style="text-align: center; line-height: 1;">
                            <img src="{get_logo_url(row['Casa'])}" width="35">
                            <p style="font-size: 22px; margin: 5px 0 0px 0; font-weight: {home_score_weight}; color: {home_score_color};">
                                {row['Score Casa']}
                            </p>
                            <p style="font-size: 11px; color: #AAA; margin: 0; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">{row['Casa']}</p>
                        </div>
                        """, unsafe_allow_html=True
                    )
                
                # Finalização do Card
                winner_text = f'Vencedor: <b style="color: #69be28;">{row["Vencedor"]}</b>' if row['Vencedor'] not in ['Empate', 'A definir'] else row["Vencedor"]
                st.markdown(f'<p style="font-size: 10px; color: #AAA; margin-top: 10px; text-align: center;">{winner_text}</p>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True) # Fecha o div do Card
                
# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    # Injeta CSS personalizado para fundo e cores gerais do texto em Dark Mode
    st.markdown("""
        <style>
            /* Altera o fundo principal */
            .stApp {
                background-color: #0E1117; 
            }
            /* Altera a cor do texto do header para Streamlit em modo dark */
            h1, h2, h3, h4, h5, h6 {
                color: #FAFAFA;
            }
            /* Melhora o contraste de tabelas e outros elementos padrão */
            .st-emotion-cache-1r6chq { /* Tabela Header */
                background-color: #262730; 
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
    
    # Carrega dados do arquivo local OU da API (depende se o arquivo foi passado ou não)
    # Para demonstração, mantém a busca na API, mas o usuário pode usar o arquivo local
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
    
    # --- TABELAS DETALHADAS ---
    
    # 1. Jogos em Andamento (Ao Vivo)
    st.header("🔴 Jogos Ao Vivo (Em Andamento)")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        # Usa o novo layout de cards também para os jogos ao vivo, se desejar
        display_final_results_styled(df_in_progress)
        
        # Ou se preferir manter a tabela simples:
        # st.dataframe(
        #     df_in_progress[['Jogo', 'Detalhe Status', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante']],
        #     hide_index=True,
        #     use_container_width=True
        # )
    else:
        st.info("Nenhum jogo em andamento no momento.")

    st.markdown("---")

    # 2. Resultados Recentes (Finalizados) - COM NOVO VISUAL CUSTOMIZADO
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
