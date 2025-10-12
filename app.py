import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 
import matplotlib.pyplot as plt 

# Configuração da página
st.set_page_config(
    page_title="NFL 2025 Eventos e Evolução W/L",
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
    Extrai e formata os dados principais de um único evento de forma ultra-robusta.
    """
    
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
        
        # Extrai o texto de todos os campos de status
        status_en = status_type.get('description', '')
        short_detail = status_type.get('shortDetail', '')
        detail = status_type.get('detail', '')
        
        # --- FIX DEFINITIVO: Análise de Texto Pura ---
        # Concatena todos os textos importantes para verificar 'final'
        status_text_check = f"{status_en} {short_detail} {detail}".lower()

        if 'final' in status_text_check:
            # Se a palavra 'final' está presente, o jogo está concluído.
            if 'ot' in status_text_check or 'overtime' in status_text_check:
                status_pt = 'Finalizado (OT)'
            else:
                status_pt = 'Finalizado'
        elif status_type.get('state') == 'in':
            status_pt = 'Em Andamento'
        elif status_type.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
            # Fallback para outros status (ex: Postponed)
            status_pt = status_en 
        # --- FIM FIX DEFINITIVO ---

        
        detail_status_raw = comp.get('status', {}).get('detail')
        if detail_status_raw:
            detail_status = detail_status_raw
        
        # --- LÓGICA DE CONSTRUÇÃO DO DETALHE STATUS ---
        if status_pt == 'Em Andamento' and (detail_status == 'N/A' or not detail_status_raw):
            clock = comp.get('status', {}).get('displayClock', '')
            period_num = comp.get('status', {}).get('period', 0)
            period_name = get_period_name(period_num)
            
            if clock and period_name:
                detail_status = f"{clock} - {period_name}"
            elif status_type.get('shortDetail'):
                detail_status = status_type.get('shortDetail', 'Em Andamento')
        elif detail_status == 'N/A' and status_type.get('shortDetail'):
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
        
        home_display_name = home_team.get('team', {}).get('displayName', 'Time Casa')
        away_display_name = away_team.get('team', {}).get('displayName', 'Time Visitante')
            
        # Determinação do Vencedor (só ocorre se o status_pt for Finalizado)
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
            'Vencedor': winner_team,
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
            'Casa': 'ERRO DE PROCESSAMENTO',
            'Visitante': 'ERRO DE PROCESSAMENTO',
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

# --- 3. FUNÇÃO: CALCULA EVOLUÇÃO W/L ---

def process_for_win_loss_evolution(df_events):
    """Calcula as vitórias e derrotas acumuladas para cada time."""
    
    # Este filtro usa o Status traduzido, que agora está garantido como 'Finalizado' se houver 'Final' no texto.
    df_results = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].copy()
    
    if df_results.empty:
        return pd.DataFrame()
    
    df_results['Data_dt'] = pd.to_datetime(df_results['Data'], format='%d/%m/%Y', errors='coerce')
    df_results = df_results.sort_values(by='Data_dt').reset_index(drop=True)

    evolution_data = []
    for index, row in df_results.iterrows():
        casa = row['Casa']
        visitante = row['Visitante']
        vencedor = row['Vencedor']
        
        # Atribuição de W/L (+1 para Vitoria, -1 para Derrota)
        if vencedor == casa:
            evolution_data.append({'Time': casa, 'Data_Jogo': row['Data_dt'], 'Delta': 1})
            evolution_data.append({'Time': visitante, 'Data_Jogo': row['Data_dt'], 'Delta': -1})
        elif vencedor == visitante:
            evolution_data.append({'Time': visitante, 'Data_Jogo': row['Data_dt'], 'Delta': 1})
            evolution_data.append({'Time': casa, 'Data_Jogo': row['Data_dt'], 'Delta': -1})

    df_evo = pd.DataFrame(evolution_data)
    if df_evo.empty:
        return pd.DataFrame()
        
    df_evo = df_evo.sort_values(by=['Time', 'Data_Jogo'])
    df_evo['Saldo Acumulado'] = df_evo.groupby('Time')['Delta'].cumsum()
    df_evo['Total Jogos'] = df_evo.groupby('Time').cumcount() + 1
    
    return df_evo[['Time', 'Data_Jogo', 'Saldo Acumulado', 'Total Jogos']]

# --- 4. FUNÇÃO: PLOTAGEM (Matplotlib) ---

def plot_win_loss_evolution(df_evo, selected_teams):
    """Cria o gráfico de evolução W/L (Matplotlib) mostrando o saldo acumulado (W-L)."""
    
    df_plot = df_evo[df_evo['Time'].isin(selected_teams)]
    
    if df_plot.empty:
        st.info("Nenhum time selecionado ou nenhum dado disponível.")
        return
    
    # Cria a figura e o eixo do Matplotlib
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Itera sobre os times selecionados para plotar as linhas
    for team in selected_teams:
        team_data = df_plot[df_plot['Time'] == team]
        ax.plot(
            team_data['Total Jogos'], 
            team_data['Saldo Acumulado'], 
            marker='o', 
            label=team,
            linestyle='-'
        )

    # Linha de base para 0
    ax.axhline(0, color='gray', linestyle='--') 
    
    # Configuração do gráfico
    ax.set_title('Evolução do Saldo W-L (Vitórias - Derrotas)', fontsize=14)
    ax.set_xlabel('Jogos Disputados', fontsize=12)
    ax.set_ylabel('Saldo Acumulado (W - L)', fontsize=12)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(title='Time', loc='upper left')
    
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))

    # Exibe o gráfico no Streamlit
    st.pyplot(fig)
    plt.close(fig) 


# --- 5. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

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
    
    # --- GRÁFICO DE EVOLUÇÃO W/L (Matplotlib) ---
    st.header("📈 Evolução do Saldo W-L")
    
    df_evo = process_for_win_loss_evolution(df_events)
    
    if df_evo.empty:
        st.info("A API não retornou jogos **finalizados** válidos para o cálculo. O gráfico aparecerá com todos os times assim que os dados forem carregados corretamente.")
    else:
        all_teams = sorted(df_evo['Time'].unique().tolist())
        
        # Seleciona TODOS os times por padrão
        default_teams = all_teams 
        
        selected_teams = st.sidebar.multiselect(
            "Selecione os Times para o Gráfico de Saldo W-L:",
            options=all_teams,
            default=default_teams, 
            key='team_selector_mpl'
        )
        
        plot_win_loss_evolution(df_evo, selected_teams)
    
    st.markdown("---")

    # --- TABELAS DETALHADAS ---
    
    # 1. Jogos em Andamento (Ao Vivo)
    st.header("🔴 Jogos Ao Vivo")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    
    if not df_in_progress.empty:
        st.dataframe(
            df_in_progress[['Jogo', 'Detalhe Status', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante']],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum jogo em andamento no momento.")


    # 2. Resultados Recentes (Finalizados)
    st.header("✅ Resultados Finais")
    df_finalized = df_events[df_events['Status'].str.startswith('Finalizado', na=False)].sort_values(by='Data', ascending=False)
    
    if not df_finalized.empty:
        results_df = df_finalized[['Data', 'Hora', 'Jogo', 'Vencedor', 'Score Casa', 'Score Visitante', 'Detalhe Status']].copy()
        
        st.dataframe(
            results_df,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Nenhum resultado finalizado encontrado.")


if __name__ == '__main__':
    main()
