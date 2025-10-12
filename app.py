import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 

# Configuração da página
st.set_page_config(
    page_title="NFL Dashboard",
    layout="wide", # Essencial para que as colunas laterais tenham largura
    initial_sidebar_state="collapsed" 
)

# --- A SEÇÃO 0 (INJEÇÃO DE CSS) FOI REMOVIDA PARA EVITAR O BUG ---

# --- 1. CONFIGURAÇÃO DE LOGOS E API ---

API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# Mapeamento para garantir que abreviações sejam traduzidas corretamente para a URL do logo
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin", 
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "det": "det", "GB": "gb", 
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar", 
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", 
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten", 
    "WAS": "was", "ARI": "ari"
}

def get_logo_url(team_abbr):
    """Gera a URL do logo da equipe a partir da abreviação."""
    base_url = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/"
    slug = LOGO_MAP.get(team_abbr.upper(), 'nfl') # Usa 'nfl' como fallback
    return f"{base_url}{slug}.png&h=40&w=40"


# --- 2. FUNÇÕES AUXILIARES DE PROCESSAMENTO DE DADOS ---

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
    Extrai e formata os dados principais de um único evento de forma ultra-robusta.
    """
    
    # Valores de segurança (default)
    data_formatada = "N/A"
    hora_formatada = "N/A"
    status_pt = "N/A"
    winner_team = "A definir"
    detail_status = "N/A" 
    
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
        status_type = comp.get('status', {}).get('type', {})
        status_en = status_type.get('description')
        
        status_map = {
            'Final': 'Finalizado',
            'Final/OT': 'Finalizado (OT)',
            'In Progress': 'Em Andamento',
            'Scheduled': 'Agendado'
        }
        status_pt = status_map.get(status_en, status_en)
        
        # Tentativa de extração do Detalhe Status da API
        detail_status_raw = comp.get('status', {}).get('detail')
        if detail_status_raw:
            detail_status = detail_status_raw
        
        # --- LÓGICA DE CORREÇÃO/CONSTRUÇÃO DO DETALHE STATUS (Fallback) ---
        if status_pt == 'Em Andamento' and (detail_status == 'N/A' or not detail_status_raw):
            clock = comp.get('status', {}).get('displayClock', '')
            period_num = comp.get('status', {}).get('period', 0)
            period_name = get_period_name(period_num)
            
            if clock and period_name:
                detail_status = f"{clock} - {period_name}"
            elif status_type.get('shortDetail'):
                # Último fallback, usando shortDetail (ex: "Q3")
                detail_status = status_type.get('shortDetail', 'Em Andamento')
        elif detail_status == 'N/A' and status_type.get('shortDetail'):
             # Para outros status sem detail, o shortDetail pode ser melhor que N/A
            detail_status = status_type.get('shortDetail', 'N/A')
        
        
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
        home_score = home_team.get('score', {}).get('displayValue', '0')
        away_score = away_team.get('score', {}).get('displayValue', '0')
        
        # Usando a abreviação do time para os logos
        home_abbr = home_team.get('team', {}).get('abbreviation', 'N/A')
        away_abbr = away_team.get('team', {}).get('abbreviation', 'N/A')

        home_display_name = home_team.get('team', {}).get('displayName', 'Time Casa')
        away_display_name = away_team.get('team', {}).get('displayName', 'Time Visitante')
            
        # Determinação do Vencedor
        if status_pt.startswith('Finalizado'):
            try:
                if home_score.isdigit() and away_score.isdigit():
                    if float(home_score) > float(away_score):
                        winner_team = home_team.get('team', {}).get('abbreviation', home_display_name)
                    elif float(away_score) > float(home_score):
                        winner_team = away_team.get('team', {}).get('abbreviation', away_display_name)
                    else:
                        winner_team = "Empate"
                else:
                    winner_team = "N/A"
            except Exception:
                winner_team = "N/A"


        return {
            'Jogo': event.get('name', 'N/A'),
            'Data': data_formatada,
            'Hora': hora_formatada,
            'Status': status_pt,
            'Casa': home_display_name,
            'Visitante': away_display_name,
            'Abrev. Casa': home_abbr,
            'Abrev. Visitante': away_abbr,
            'Vencedor': winner_team,
            'Score Casa': home_score,
            'Score Visitante': away_score,
            'Detalhe Status': detail_status
        }
        
    except Exception as e:
        # Linha de ERRO para garantir que o app não quebre
        return {
            'Jogo': 'Erro de Estrutura de Dados',
            'Data': 'N/A',
            'Hora': 'N/A',
            'Status': 'ERRO',
            'Casa': 'ERRO DE PROCESSAMENTO',
            'Visitante': 'ERRO DE PROCESSAMENTO',
            'Abrev. Casa': 'N/A',
            'Abrev. Visitante': 'N/A',
            'Vencedor': 'N/A',
            'Score Casa': 'N/A',
            'Score Visitante': 'N/A',
            'Detalhe Status': f'Falha na extração: {type(e).__name__}'
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
    
    if not events_list:
        st.info("Nenhum evento encontrado na API de Events para 2025.")
        return pd.DataFrame()
        
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    df = pd.DataFrame(events_data)
    return df

# --- FUNÇÃO DE ESTILIZAÇÃO (CARDS) ---

def display_final_results_styled(df_results):
    """Exibe resultados em um formato de card estilizado com HTML/CSS e colunas."""
    
    # Define o número de colunas (3 cards por linha)
    cols = st.columns(3)
    
    # CSS Customizado para Cards (Mantido aqui, mas pode ser removido e colocado em um st.markdown inicial se necessário)
    card_styles = """
    <style>
    .result-card {
        border: 1px solid #ddd;
        padding: 15px;
        margin-bottom: 10px;
        border-radius: 8px;
        background-color: #f9f9f9;
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
    """
    st.markdown(card_styles, unsafe_allow_html=True) # Injeta os estilos dos cards aqui

    for i, row in df_results.iterrows():
        col = cols[i % 3] # Distribui os cards entre as 3 colunas
        
        home_logo_url = get_logo_url(row['Abrev. Casa'])
        away_logo_url = get_logo_url(row['Abrev. Visitante'])
        
        status_text = row['Detalhe Status']
        if row['Status'].startswith('Finalizado'):
            status_style = 'color: green; font-weight: bold;'
        elif row['Status'] == 'Agendado':
             status_style = 'color: orange; font-weight: bold;'
        else:
            status_style = 'color: blue; font-weight: bold;'


        # Monta o HTML do card
        card_html = f"""
        <div class="result-card">
            <div style="text-align: center; margin-bottom: 10px; {status_style}">
                {status_text}
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                <div class="home-team" style="display: flex; align-items: center;">
                    <img src="{home_logo_url}" style="margin-right: 5px;"/>
                    {row['Abrev. Casa']} ({row['Casa']})
                </div>
                <div class="score">{row['Score Casa']}</div>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="away-team" style="display: flex; align-items: center;">
                    <img src="{away_logo_url}" style="margin-right: 5px;"/>
                    {row['Abrev. Visitante']} ({row['Visitante']})
                </div>
                <div class="score">{row['Score Visitante']}</div>
            </div>
            
            <div class="game-info" style="text-align: center; margin-top: 10px;">
                {row['Data']} às {row['Hora']}
            </div>
        </div>
        """
        
        col.markdown(card_html, unsafe_allow_html=True)


# --- 3. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():
    
    league_name, current_season = get_league_metadata()
    
    # NOVO: Define colunas laterais vazias para criar a margem centralizada
    # 15% (margem esquerda) | 70% (conteúdo) | 15% (margem direita)
    col_left, col_center, col_right = st.columns([15, 70, 15]) 

    # Todo o conteúdo do dashboard deve ir para a coluna central
    with col_center:
        st.title(f"🏈 Dashboard {league_name} - {current_season}")
        st.markdown("---")
        
        st.sidebar.header("Controles")
        st.sidebar.markdown(f"**Liga:** {league_name}")
        st.sidebar.markdown(f"**Temporada:** {current_season} (Todos os Eventos)")
        st.sidebar.markdown("---")
        
        if st.sidebar.button("Recarregar Dados Agora"):
            st.rerun() 
            
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
        
        # --- RESULTADOS RECENTES (CARDS) ---
        st.header("✅ Resultados Recentes")
        df_finalized = df_events[
            df_events['Status'].str.startswith('Finalizado', na=False)
        ].sort_values(by='Data', ascending=False)

        if not df_finalized.empty:
            # Exibe apenas os 9 resultados mais recentes nos cards
            display_final_results_styled(df_finalized.head(9))
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
            # Reutiliza a função de cards para agendados
            display_final_results_styled(df_scheduled.head(9))
        else:
            st.markdown('<p style="color:#888; text-align: center; margin-bottom: 1rem;">Nenhum jogo agendado nos dados fornecidos.</p>', unsafe_allow_html=True)

        # SEPARADOR ENTRE AGENDADOS E HISTÓRICO COMPLETO
        st.markdown("---")

        # --- HISTÓRICO COMPLETO DA TEMPORADA (TABELA) ---
        st.header("📚 Histórico Completo da Temporada")
        st.dataframe(
            df_events[['Data', 'Hora', 'Jogo', 'Status', 'Vencedor', 'Score Casa', 'Score Visitante', 'Detalhe Status']],
            use_container_width=True
        )


if __name__ == '__main__':
    main()
