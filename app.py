import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 
import altair as alt # NOVO: Importação necessária para o gráfico evolutivo

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

# --- 3. NOVA FUNÇÃO: CALCULA EVOLUÇÃO W/L ---

def process_for_win_loss_evolution(df_events):
    """Calcula as vitórias e derrotas acumuladas para cada time."""
    
    # 1. Filtra apenas jogos finalizados
    df_results = df_events[
        df_events['Status'].str.startswith('Finalizado', na=False)
    ].copy()
    
    if df_results.empty:
        return pd.DataFrame()
    
    # Ordena por Data para garantir a ordem correta da evolução
    df_results['Data_dt'] = pd.to_datetime(df_results['Data'], format='%d/%m/%Y', errors='coerce')
    df_results = df_results.sort_values(by='Data_dt').reset_index(drop=True)

    evolution_data = []
    for index, row in df_results.iterrows():
        casa = row['Casa']
        visitante = row['Visitante']
        vencedor = row['Vencedor']
        
        # Cria dois registros por jogo (um para cada time)
        if vencedor == casa:
            evolution_data.append({'Time': casa, 'Jogo': row['Jogo'], 'Resultado': 'Vitória', 'Data_Jogo': row['Data_dt'], 'Tipo': 'Vitórias', 'Contagem': 1})
            evolution_data.append({'Time': visitante, 'Jogo': row['Jogo'], 'Resultado': 'Derrota', 'Data_Jogo': row['Data_dt'], 'Tipo': 'Derrotas', 'Contagem': 1})
        elif vencedor == visitante:
            evolution_data.append({'Time': visitante, 'Jogo': row['Jogo'], 'Resultado': 'Vitória', 'Data_Jogo': row['Data_dt'], 'Tipo': 'Vitórias', 'Contagem': 1})
            evolution_data.append({'Time': casa, 'Jogo': row['Jogo'], 'Resultado': 'Derrota', 'Data_Jogo': row['Data_dt'], 'Tipo': 'Derrotas', 'Contagem': 1})
        # Empates (são ignorados na contagem W/L para simplificar o gráfico)

    df_evo = pd.DataFrame(evolution_data)
        
    # 2. Calcula o acumulado por time e por tipo (Vitórias/Derrotas)
    df_evo['Acumulado'] = df_evo.groupby(['Time', 'Tipo'])['Contagem'].cumsum()
    
    # Adiciona um índice de jogo (sequencial por time) para o eixo X do gráfico
    df_evo['Total Jogos'] = df_evo.groupby('Time').cumcount().floordiv(2) + 1 # Divide por 2 porque cada jogo gera 2 linhas (W e L)
    
    return df_evo[['Time', 'Jogo', 'Data_Jogo', 'Tipo', 'Acumulado', 'Total Jogos']]

# --- 4. NOVA FUNÇÃO: PLOTAGEM (Gráfico de Área Empilhada) ---

def plot_win_loss_evolution(df_evo, selected_teams):
    """Cria o gráfico de evolução W/L (área empilhada) usando Altair."""
    
    # Filtra os times selecionados
    df_plot = df_evo[df_evo['Time'].isin(selected_teams)]
    
    if df_plot.empty:
        st.info("Nenhum time selecionado ou nenhum dado disponível para o(s) time(s) selecionado(s).")
        return

    # Ordem das cores para manter Vitórias em cima e Derrotas em baixo
    color_scale = alt.Scale(domain=['Vitórias', 'Derrotas'], range=['#69C54F', '#D94452'])

    chart = alt.Chart(df_plot).mark_area().encode(
        # Eixo X: Total de Jogos
        x=alt.X('Total Jogos:Q', axis=alt.Axis(title='Jogos Disputados', tickMinStep=1)),
        # Eixo Y: Acumulado (Empilhado)
        y=alt.Y('Acumulado:Q', stack='zero', axis=alt.Axis(title='Vitórias (Acima) / Derrotas (Abaixo)')),
        # Cor: Tipo de resultado (Vitórias ou Derrotas)
        color=alt.Color('Tipo:N', scale=color_scale, legend=alt.Legend(title="Resultado")),
        # Divisão por Linha (para cada time)
        row=alt.Row('Time:N', header=alt.Header(titleOrient="bottom", labelOrient="bottom")),
        # Tooltip para interatividade
        tooltip=['Time', 'Total Jogos', 'Tipo', 'Acumulado']
    ).properties(
        title='Evolução Acumulada de Vitórias (W) e Derrotas (L)'
    ).interactive()

    st.altair_chart(chart, use_container_width=True)


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
    
    # ... (outras métricas omitidas para brevidade, mas estão no código)

    col1, col2 = st.columns(2)
    col1.metric("Total de Jogos", total_games)
    col2.metric("Finalizados", finalizados)
    # ... (outras colunas)

    st.markdown("---")
    
    # --- GRÁFICO DE EVOLUÇÃO W/L ---
    st.header("📈 Gráfico de Evolução de W-L Acumulado")
    
    df_evo = process_for_win_loss_evolution(df_events)
    
    # CORREÇÃO CRÍTICA: Checagem de segurança para evitar o KeyError
    if df_evo.empty:
        st.info("Não há dados de jogos finalizados para calcular o gráfico de evolução.")
    else:
        # Lógica de Plotagem (só executa se df_evo não estiver vazio)
        all_teams = sorted(df_evo['Time'].unique().tolist())
        
        # Seleciona os primeiros 5 times por padrão
        default_teams = all_teams[:5]
        
        selected_teams = st.sidebar.multiselect(
            "Selecione os Times para o Gráfico:",
            options=all_teams,
            default=default_teams,
            key='team_selector_evo'
        )
        
        plot_win_loss_evolution(df_evo, selected_teams)
    
    st.markdown("---")

    # --- TABELAS DETALHADAS ---
    
    # 1. Jogos em Andamento (Ao Vivo)
    st.header("🔴 Jogos Ao Vivo")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Detalhe Status', ascending=False)
    # ... (restante do código das tabelas)
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
