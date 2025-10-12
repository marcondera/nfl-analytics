import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
import requests 
from dateutil.parser import isoparse 

# Configuração da página
st.set_page_config(
    page_title="NFL 2025 Eventos e Resultados",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. CONFIGURAÇÃO DA API (LINK ESTÁVEL) ---
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"


# --- 2. FUNÇÕES DE BUSCA E PROCESSAMENTO DE DADOS ---

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
    """
    
    data_formatada = "N/A"
    hora_formatada = "N/A"
    status_pt = "N/A"
    winner_team_abbr = "A definir"
    detail_status = "N/A" 
    home_team_abbr = "N/A"
    away_team_abbr = "N/A"
    home_team_color = "000000" # Cor padrão Preto (melhor que cinza claro)
    away_team_color = "000000"
    
    try:
        comp = event['competitions'][0]
        date_iso = comp.get('date')

        # --- CORREÇÃO DE DATA/HORA (Usando isoparse) ---
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
        
        # --- LÓGICA DE CONSTRUÇÃO DO DETALHE STATUS (Para jogos 'Em Andamento') ---
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
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A', 'Hora': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': f'Falha na extração: {type(e).__name__}',
            'Home Color': '333333', 'Away Color': '333333'
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca e normaliza os dados da API de Events da ESPN (2025)."""
    
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
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    if not events_data:
        st.warning("Não foi possível extrair dados válidos dos eventos após o processamento.")
        return pd.DataFrame()
        
    df = pd.DataFrame(events_data)
    return df

# --- 3. FUNÇÃO DE RENDERIZAÇÃO CUSTOMIZADA (STÁVEL) ---

def display_final_results_styled(df_finalized):
    """
    Renderiza os resultados finais como cards usando st.container e st.columns para estabilidade.
    """
    
    for index, row in df_finalized.iterrows():
        
        is_home_winner = row['Vencedor'] == row['Casa']
        is_away_winner = row['Vencedor'] == row['Visitante']
        is_draw = row['Vencedor'] == 'Empate'
        
        # Cor de fundo sutil para todo o card
        if is_home_winner or is_away_winner:
            container_color = "#f3f9f3" # Verde claro para vitória
        elif is_draw:
            container_color = "#fffbe6" # Amarelo claro para empate
        else:
            container_color = "#f7f7f7"
        
        # Usa um contêiner para cada jogo (o 'card')
        with st.container(border=True):
            st.markdown(f'<div style="background-color: {container_color}; border-radius: 8px; padding: 15px;">', unsafe_allow_html=True)

            # Informação do jogo (Data/Status)
            st.caption(f"**{row['Data']}** | {row['Detalhe Status']}")
            
            # Layout em Colunas: Time Visitante | VS | Time Casa
            col_away, col_vs, col_home = st.columns([4, 1, 4])

            # --- Coluna Time Visitante ---
            with col_away:
                away_score_weight = "bold" if is_away_winner else "normal"
                away_score_color = "#000000" if is_away_winner else "#666666"

                st.markdown(
                    f"""
                    <div style="
                        background-color: #{row['Away Color']}; 
                        color: white; 
                        padding: 8px; 
                        border-radius: 6px; 
                        text-align: center; 
                        font-size: 18px; 
                        font-weight: bold;
                    ">
                        {row['Visitante']}
                    </div>
                    <div style="text-align: center; margin-top: 10px; font-size: 32px; font-weight: {away_score_weight}; color: {away_score_color};">
                        {row['Score Visitante']}
                    </div>
                    """, unsafe_allow_html=True
                )

            # --- Coluna Central (VS) ---
            with col_vs:
                st.markdown('<div style="font-size: 18px; text-align: center; margin-top: 30px; color: #999;">VS</div>', unsafe_allow_html=True)

            # --- Coluna Time Casa ---
            with col_home:
                home_score_weight = "bold" if is_home_winner else "normal"
                home_score_color = "#000000" if is_home_winner else "#666666"

                st.markdown(
                    f"""
                    <div style="
                        background-color: #{row['Home Color']}; 
                        color: white; 
                        padding: 8px; 
                        border-radius: 6px; 
                        text-align: center; 
                        font-size: 18px; 
                        font-weight: bold;
                    ">
                        {row['Casa']}
                    </div>
                    <div style="text-align: center; margin-top: 10px; font-size: 32px; font-weight: {home_score_weight}; color: {home_score_color};">
                        {row['Score Casa']}
                    </div>
                    """, unsafe_allow_html=True
                )
            
            st.markdown('</div>', unsafe_allow_html=True) # Fecha o div de background
        
# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    league_name, current_season = get_league_metadata()
    
    st.title(f"🏈 Dashboard {league_name} - {current_season}")
    st.markdown("---")
    
    st.sidebar.header("Controles")
    st.sidebar.markdown(f"**Liga:** {league_name}")
    st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("Recarregar Dados Agora"):
        st.rerun() 
        
    # Carrega todos os eventos
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
    
    # 1. Jogos em Andamento (Ao Vivo) - Mantido como Tabela Simples
    st.header("🔴 Jogos Ao Vivo (Temporada Atual)")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        st.dataframe(
            df_in_progress[['Jogo', 'Detalhe Status', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo em andamento no momento.")

    st.markdown("---")

    # 2. Resultados Recentes (Finalizados) - NOVO VISUAL CUSTOMIZADO
    st.header("✅ Resultados Finais (Temporada Atual)")
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        # Chama a função que renderiza os cards visuais
        display_final_results_styled(df_finalized)
    else:
        st.info("Nenhum resultado finalizado encontrado.")


if __name__ == '__main__':
    main()
