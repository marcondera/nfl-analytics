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
    Extrai e formata os dados principais de um único evento.
    """
    
    data_formatada = "N/A"
    hora_formatada = "N/A"
    status_pt = "N/A"
    winner_team_abbr = "A definir" # Usaremos a abreviação do time para o vencedor
    detail_status = "N/A" 
    home_team_abbr = "N/A"
    away_team_abbr = "N/A"
    
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
        # Garante que o score seja tratado como int para cálculos e comparações
        home_score = int(home_team.get('score', {}).get('value', 0.0))
        away_score = int(away_team.get('score', {}).get('value', 0.0))
        
        home_display_name = home_team.get('team', {}).get('displayName', 'Time Casa')
        away_display_name = away_team.get('team', {}).get('displayName', 'Time Visitante')
        
        home_team_abbr = home_team.get('team', {}).get('abbreviation', home_display_name)
        away_team_abbr = away_team.get('team', {}).get('abbreviation', away_display_name)
            
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
            'Casa': home_team_abbr, # Usando a abreviação
            'Visitante': away_team_abbr, # Usando a abreviação
            'Vencedor': winner_team_abbr,
            'Score Casa': home_score,
            'Score Visitante': away_score,
            'Detalhe Status': detail_status
        }
        
    except Exception as e:
        return {
            'Jogo': 'Erro de Estrutura de Dados',
            'Data': 'N/A',
            'Hora': 'N/A',
            'Status': 'ERRO',
            'Casa': 'ERRO',
            'Visitante': 'ERRO',
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
    events_data = [get_event_data(e) for e in events_list]
    events_data = [item for item in events_data if item is not None]
        
    if not events_data:
        st.warning("Não foi possível extrair dados válidos dos eventos após o processamento.")
        return pd.DataFrame()
        
    df = pd.DataFrame(events_data)
    return df


# --- FUNÇÕES DE ESTILIZAÇÃO DO DATAFRAME ---

def highlight_winner(row):
    """
    Formata a linha:
    - Coloca em negrito o nome do vencedor na coluna 'Placar Final'.
    - Destaca a linha inteira em verde claro para vitória ou cinza para derrota.
    """
    styles = [''] * len(row)
    vencedor = row['Vencedor']
    casa = row['Casa']
    visitante = row['Visitante']
    placar_final = row['Placar Final']
    
    if vencedor == 'Empate':
        # Sem destaque especial para empate
        return styles
        
    # Coloca em negrito o nome do vencedor no placar
    if casa == vencedor:
        placar_estilizado = placar_final.replace(vencedor, f"**{vencedor}**")
        row['Placar Final'] = placar_estilizado
    elif visitante == vencedor:
        placar_estilizado = placar_final.replace(vencedor, f"**{vencedor}**")
        row['Placar Final'] = placar_estilizado
        
    return styles # Retorna o estilo da linha (pode ser ajustado para cores de fundo se desejado)


def format_final_results(df_finalized):
    """
    Aplica a formatação condicional usando o Pandas Styler.
    """
    
    # 1. Cria a coluna 'Placar Final' formatada (Ex: LAR 25 x 30 SEA)
    df_finalized['Placar Final'] = (
        df_finalized['Casa'] + ' ' + 
        df_finalized['Score Casa'].astype(str) + 
        ' x ' + 
        df_finalized['Score Visitante'].astype(str) + ' ' + 
        df_finalized['Visitante']
    )
    
    # 2. Seleciona e renomeia as colunas que serão exibidas
    df_display = df_finalized[['Data', 'Hora', 'Jogo', 'Vencedor', 'Placar Final']].copy()
    df_display.columns = ['Data', 'Hora', 'Partida', 'Vencedor', 'Placar']
    
    # 3. Formatação usando Styler para negrito e cores
    
    # Função auxiliar que aplica negrito no Placar baseado no vencedor
    def apply_styles(s):
        is_winner = s['Vencedor']
        placar = s['Placar']
        
        # Verifica se é um jogo com vencedor
        if is_winner not in ['N/A', 'Empate']:
            # Aplica negrito no time vencedor dentro da string 'Placar'
            if s['Partida'].startswith(s['Vencedor']): # Se o jogo começar com o vencedor (Regra de Nome Completo)
                placar = placar.replace(is_winner, f"**{is_winner}**")
            else: # Tenta encontrar o vencedor em qualquer lugar da string do placar
                # Como 'Placar' é 'LAR 25 x 30 SEA', podemos usar a abreviação
                placar = placar.replace(is_winner, f"**{is_winner}**")

        # Se o time do placar final for o vencedor, colore a célula do 'Vencedor'
        styles = pd.Series('', index=s.index)
        
        # Aplicamos cor de fundo na célula 'Vencedor'
        if is_winner != 'N/A' and is_winner != 'Empate':
            styles['Vencedor'] = 'background-color: #03a9f4; color: white; font-weight: bold;' # Azul da NFL
        elif is_winner == 'Empate':
             styles['Vencedor'] = 'background-color: #fdd835; color: black;' # Amarelo para Empate
             
        # Atualiza o Placar com negrito (isso só é possível se usarmos uma função `apply` na linha)
        s['Placar'] = placar
        
        return styles


    # Usamos st.markdown e o Styler para aplicar a formatação
    # NOTA: O Streamlit não renderiza negrito/markdown dentro de `st.dataframe` formatado por Styler.
    # A melhor prática moderna é usar st.dataframe sem o Styler, mas usando `column_config`
    # Infelizmente, `column_config` não suporta formatação condicional como queremos aqui.
    
    # Abordagem 1: Usar .apply para cor de fundo (Mais simples)
    def style_winner_cell(val):
        """Formata apenas a célula do Vencedor."""
        if val not in ['N/A', 'Empate']:
            return 'background-color: #03a9f4; color: white; font-weight: bold;'
        elif val == 'Empate':
            return 'background-color: #fdd835; color: black;'
        return None

    # Abordagem 2: Usar o Styler
    styled_df = (
        df_display.style
        .applymap(style_winner_cell, subset=['Vencedor'])
        .hide(axis='index')
    )
    
    return styled_df


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
    
    # 1. Jogos em Andamento (Ao Vivo)
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

    # 2. Resultados Recentes (Finalizados) - COM ESTILO VISUAL
    st.header("✅ Resultados Finais (Temporada Atual)")
    df_finalized = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        # Aplica a formatação visual e gera o Styler Object
        styled_final_results = format_final_results(df_finalized)
        
        # Exibe o dataframe estilizado
        st.dataframe(
            styled_final_results,
            use_container_width=True,
            column_config={
                "Vencedor": st.column_config.Column(
                    "Vencedor",
                    help="Time que venceu a partida",
                    width="small"
                ),
                "Placar": st.column_config.Column(
                    "Placar Final",
                    help="Score da Partida (Casa x Visitante)"
                )
            }
        )
    else:
        st.info("Nenhum resultado finalizado encontrado.")


if __name__ == '__main__':
    main()
