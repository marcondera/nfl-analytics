import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import re
import math
from io import StringIO

# --- CONFIGURAÇÃO E ESTILO GLOBAL (Streamlit Nativo) ---

CURRENT_PFR_YEAR = 2025 

# Configurações iniciais do Streamlit (título, layout)
# ATENÇÃO: Adicionando unsafe_allow_html=True nas marcações para forçar a centralização precisa dos scores.
st.set_page_config(page_title=f"🏈 NFL Dashboard {CURRENT_PFR_YEAR}", layout="wide", page_icon="🏈")


# Endpoints
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# Mapa de Logos, Nomes e Divisões
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

PFR_NAME_MAP_REVERSE = {
    'SF': '49ers', 'BUF': 'Bills', 'ATL': 'Falcons', 'BAL': 'Ravens', 'CAR': 'Panthers', 
    'CIN': 'Bengals', 'CHI': 'Bears', 'CLE': 'Browns', 'DAL': 'Cowboys', 'DEN': 'Broncos', 
    'DET': 'Lions', 'GB': 'Packers', 'HOU': 'Texans', 'IND': 'Colts', 'JAX': 'Jaguars', 
    'KC': 'Chiefs', 'LAC': 'Chargers', 'LAR': 'Rams', 'LV': 'Raiders', 'MIA': 'Dolphins', 
    'MIN': 'Vikings', 'NE': 'Patriots', 'NO': 'Saints', 'NYG': 'Giants', 'NYJ': 'Jets', 
    'PHI': 'Eagles', 'PIT': 'Steelers', 'SEA': 'Seahawks', 'TB': 'Buccaneers', 'TEN': 'Titans',
    'ARI': 'Cardinals', 'WSH': 'Commanders'
}

TEAM_CONFERENCE_DIVISION_MAP = {
    'BUF': {'conf': 'AFC', 'div': 'East'}, 'MIA': {'conf': 'AFC', 'div': 'East'}, 'NE': {'conf': 'AFC', 'div': 'East'}, 'NYJ': {'conf': 'AFC', 'div': 'East'},
    'BAL': {'conf': 'AFC', 'div': 'North'}, 'CIN': {'conf': 'AFC', 'div': 'North'}, 'CLE': {'conf': 'AFC', 'div': 'North'}, 'PIT': {'conf': 'AFC', 'div': 'North'},
    'HOU': {'conf': 'AFC', 'div': 'South'}, 'IND': {'conf': 'AFC', 'div': 'South'}, 'JAX': {'conf': 'AFC', 'div': 'South'}, 'TEN': {'conf': 'AFC', 'div': 'South'},
    'DEN': {'conf': 'AFC', 'div': 'West'}, 'KC': {'conf': 'AFC', 'div': 'West'}, 'LV': {'conf': 'AFC', 'div': 'West'}, 'LAC': {'conf': 'AFC', 'div': 'West'},

    'DAL': {'conf': 'NFC', 'div': 'East'}, 'NYG': {'conf': 'NFC', 'div': 'East'}, 'PHI': {'conf': 'NFC', 'div': 'East'}, 'WSH': {'conf': 'NFC', 'div': 'East'},
    'CHI': {'conf': 'NFC', 'div': 'North'}, 'DET': {'conf': 'NFC', 'div': 'North'}, 'GB': {'conf': 'NFC', 'div': 'North'}, 'MIN': {'conf': 'NFC', 'div': 'North'},
    'ATL': {'conf': 'NFC', 'div': 'South'}, 'CAR': {'conf': 'NFC', 'div': 'South'}, 'NO': {'conf': 'NFC', 'div': 'South'}, 'TB': {'conf': 'NFC', 'div': 'South'},
    'ARI': {'conf': 'NFC', 'div': 'West'}, 'LAR': {'conf': 'NFC', 'div': 'West'}, 'SF': {'conf': 'NFC', 'div': 'West'}, 'SEA': {'conf': 'NFC', 'div': 'West'}
}

# --- FUNÇÕES AUXILIARES ---

def get_logo_url(abbreviation):
    """Gera URL do logo baseada na abreviação."""
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_team_display_name(abbr):
    """Retorna o nome curto do time para exibição (ex: 'Bills' para 'BUF')."""
    return PFR_NAME_MAP_REVERSE.get(abbr, abbr)

# --- FUNÇÕES DE CARREGAMENTO DE DADOS ---

@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse(year):
    """
    Carrega o histórico de eventos (jogos) do nflverse (via CSV),
    padronizando abreviações e tratando erros de dados.
    """
    st.info(f"⏳ Tentando carregar dados históricos do NFLverse para a temporada: **{year}**.")

    try:
        response = requests.get(NFLVERSE_GAMES_URL)
        response.raise_for_status()
        
        df = pd.read_csv(StringIO(response.text))
        
        # Garante que estamos filtrando pelo ano correto (2025)
        df_year = df[(df['season'] == year) & (df['game_type'] == 'REG')].copy()
        
        df_year['home_score'] = pd.to_numeric(df_year['home_score'], errors='coerce').fillna(0)
        df_year['away_score'] = pd.to_numeric(df_year['away_score'], errors='coerce').fillna(0)
        
        # Filtra jogos que tenham algum score (evita jogos futuros/cancelados sem pontuação)
        df_year = df_year[(df_year['home_score'] > 0) | (df_year['away_score'] > 0)].copy()

        if df_year.empty:
            st.warning(f"Nenhum jogo jogado encontrado no NFLverse para a temporada {year}. O placar estará vazio.")
            return pd.DataFrame()

        def standardize_abbr(abbr):
            """Padroniza abreviações problemáticas (ex: WAS para WSH)."""
            if abbr in ['WAS', 'WSH']:
                return 'WSH'
            if abbr not in TEAM_CONFERENCE_DIVISION_MAP:
                 # Esta abreviação não é de um time da NFL (pode ser de jogos antigos/pro-bowl/etc)
                 return None 
            return abbr

        def calculate_result(row):
            home_score = int(row['home_score'])
            away_score = int(row['away_score'])
            
            home_team = standardize_abbr(row['home_team'])
            away_team = standardize_abbr(row['away_team'])
            
            if home_team is None or away_team is None:
                return pd.Series([None] * 8)
            
            # Garante que o time com maior pontuação é o vencedor.
            if home_score >= away_score:
                winner_abbr, winner_pts = home_team, home_score
                loser_abbr, loser_pts = away_team, away_score
            else: 
                # Isso não deve acontecer se a lógica de home_score/away_score estiver correta,
                # mas é uma garantia.
                winner_abbr, winner_pts = away_team, away_score
                loser_abbr, loser_pts = home_team, home_score
            
            winner_name = get_team_display_name(winner_abbr)
            loser_name = get_team_display_name(loser_abbr)

            return pd.Series([
                row['week'], 
                f"{row['gameday']} {row['season']}", # Date_Full
                winner_name,  
                winner_abbr,  
                winner_pts, 
                loser_name,   
                loser_abbr,   
                loser_pts,
            ])

        df_results = df_year.apply(calculate_result, axis=1)
        df_results.columns = ['Week', 'Date_Full', 'Winner_PFR', 'Winner_Abbr', 'Winner_Pts', 'Loser_PFR', 'Loser_Abbr', 'Loser_Pts']
        
        df_results = df_results.dropna(subset=['Winner_Abbr', 'Week'])
        
        df_results['Week'] = pd.to_numeric(df_results['Week'], errors='coerce').astype('Int64')
        
        max_week = df_results['Week'].max() if not df_results.empty else 'N/A'
        st.success(f"✅ Dados históricos da Semana **{max_week}** carregados e processados para **{year}**.")
        return df_results
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erro de rede/acesso ao carregar o NFLverse: {e}. Verifique sua conexão ou a URL.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Erro genérico durante o processamento de dados: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600)
def load_live_events_from_espn():
    """Carrega o scoreboard atual da ESPN para verificar a semana ativa (Ano 2025 já no URL base)."""
    try:
        # A URL não precisa do ano, o endpoint da ESPN é para a temporada atual.
        response = requests.get(API_URL_SCOREBOARD) 
        response.raise_for_status()
        data = response.json()
        
        # Extrai a semana da resposta da ESPN
        week_name = data.get('week', {}).get('text', 'Semana Atual Não Definida')
        current_week = int(re.search(r'\d+', week_name).group()) if re.search(r'\d+', week_name) else None
        
        return current_week, data.get('events', [])
    except Exception:
        # Erro não crítico, apenas usa a base histórica
        return None, []

# --- FUNÇÕES DE CLASSIFICAÇÃO E EXIBIÇÃO ---

def calculate_standings(df_games):
    """Calcula Vitórias, Derrotas, Empates e PCT para cada time."""
    
    standings = {abbr: {'W': 0, 'L': 0, 'T': 0} for abbr in TEAM_CONFERENCE_DIVISION_MAP.keys()}

    for _, game in df_games.iterrows():
        winner_abbr = game['Winner_Abbr']
        loser_abbr = game['Loser_Abbr']
        winner_pts = game['Winner_Pts']
        loser_pts = game['Loser_Pts']
        
        if winner_abbr in standings and loser_abbr in standings:
            if winner_pts > loser_pts:
                standings[winner_abbr]['W'] += 1
                standings[loser_abbr]['L'] += 1
            elif winner_pts == loser_pts: # Empate (Tie)
                standings[winner_abbr]['T'] += 1
                standings[loser_abbr]['T'] += 1
            # Se for menor, a lógica de W/L já foi garantida na função de load.

    df_standings = pd.DataFrame.from_dict(standings, orient='index').reset_index().rename(columns={'index': 'Abbr'})
    
    df_standings['Conf'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('conf', 'N/A'))
    df_standings['Div'] = df_standings['Abbr'].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get('div', 'N/A'))
    
    df_standings = df_standings[df_standings['Conf'] != 'N/A'].copy()

    # Calcula PCT (Win Percentage)
    df_standings['GP'] = df_standings['W'] + df_standings['L'] + df_standings['T']
    df_standings['PCT'] = df_standings.apply(
        lambda row: (row['W'] + 0.5 * row['T']) / row['GP'] if row['GP'] > 0 else 0.000, axis=1
    )
    
    df_standings['PCT_Str'] = df_standings['PCT'].map('{:.3f}'.format)
    
    return df_standings

def display_standings(df_standings, conference_name):
    """Exibe a classificação por divisão com um visual mais limpo e organizado."""
    
    # Estilo visual melhorado: cores nos sub-títulos
    color_code = 'blue' if conference_name == 'AFC' else 'red'
    st.subheader(f":{color_code}[{conference_name} - Classificação]") 
    
    conf_df = df_standings[df_standings['Conf'] == conference_name].copy()
    
    divisions = sorted(conf_df['Div'].unique())

    for div in divisions:
        st.markdown(f"**Divisão {div}**", help="Tabela ordenada por Porcentagem de Vitória (PCT)") 
        
        div_df = conf_df[conf_df['Div'] == div].copy()
        
        div_df['Time'] = div_df['Abbr'].apply(get_team_display_name)
        div_df = div_df.sort_values(by=['PCT', 'W', 'T'], ascending=[False, False, False])
        
        display_cols = div_df[['Time', 'Abbr', 'W', 'L', 'T', 'PCT_Str']]
        
        st.dataframe(
            display_cols.rename(columns={'Abbr': 'ABBR', 'W': 'V', 'L': 'D', 'T': 'E', 'PCT_Str': 'PCT'}),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Time": "Time",
                "ABBR": st.column_config.TextColumn("Sigla", width="small"),
                "V": st.column_config.NumberColumn("Vitórias", width="extra small", format="%d"),
                "D": st.column_config.NumberColumn("Derrotas", width="extra small", format="%d"),
                "E": st.column_config.NumberColumn("Empates", width="extra small", format="%d"),
                "PCT": st.column_config.TextColumn("PCT", width="small"),
            }
        )
    st.divider() # Adiciona separador após cada conferência

def display_scoreboard(df_pfr, current_week_espn=None):
    """
    Exibe o placar formatado de forma compacta e com pontuações CENTRALIZADAS
    dentro de cada cartão de jogo, usando HTML/CSS para forçar o alinhamento.
    """

    if df_pfr.empty:
        st.info("Não há dados de jogos finalizados para esta temporada na base histórica.")
        return

    # Determinação da semana para o cabeçalho
    if current_week_espn:
        st.header(f"🗓️ Semana Atual: :green[{current_week_espn}]")
        df_display = df_pfr[df_pfr['Week'] == current_week_espn].copy()
        if df_display.empty:
             max_week = df_pfr['Week'].max()
             st.subheader(f"⚠️ Sem jogos finalizados na Semana {current_week_espn}. Mostrando a última semana jogada: **{max_week}**.")
             df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    else:
        max_week = df_pfr['Week'].max()
        st.header(f"🗓️ Última Semana Jogada: :orange[{max_week}]")
        df_display = df_pfr[df_pfr['Week'] == max_week].copy()
    
    games_list = df_display[['Week', 'Date_Full', 'Winner_Abbr', 'Loser_Abbr', 'Winner_Pts', 'Loser_Pts']].to_dict('records')

    if not games_list:
        st.info(f"Nenhum jogo encontrado para exibição nesta semana.")
        return

    # Layout de 3 cards por linha
    num_cols = 3
    
    for i in range(0, len(games_list), num_cols):
        cols = st.columns(num_cols)
        
        for j in range(num_cols):
            game_index = i + j
            if game_index < len(games_list):
                game = games_list[game_index]
                
                winner_abbr = game['Winner_Abbr']
                loser_abbr = game['Loser_Abbr']
                winner_pts = int(game['Winner_Pts'])
                loser_pts = int(game['Loser_Pts'])
                
                with cols[j]:
                    with st.container(border=True):
                        # Data do Jogo no topo
                        st.caption(f":calendar: {game['Date_Full']}")
                        
                        # Layout principal para o placar: [Vencedor] | [Scores + VS] | [Perdedor]
                        # Ajuste fino das colunas
                        col_w_info, col_scores, col_l_info = st.columns([1.5, 2.5, 1.5]) 

                        # 1. Info Vencedor
                        with col_w_info:
                            st.image(get_logo_url(winner_abbr), width=50)
                            st.markdown(f"**{winner_abbr}**")

                        # 2. Scores Centralizados - *** CORREÇÃO DE ALINHAMENTO COM HTML INLINE ***
                        with col_scores:
                            # 3 Colunas: [Score W] | [VS] | [Score L]
                            # 1.0 vs 0.5 vs 1.0 para que o VS fique bem no centro da seção de scores
                            col_score_w, col_vs_text, col_score_l = st.columns([1.0, 0.5, 1.0]) 
                            
                            # Força o alinhamento do score do Vencedor no centro da sua coluna
                            with col_score_w:
                                st.markdown(f"<h3 style='text-align: center; color: #1E90FF; font-size: 24px;'>{winner_pts}</h3>", 
                                            unsafe_allow_html=True)
                            
                            # Força o alinhamento do VS no centro
                            with col_vs_text:
                                # Adiciona um pequeno margin-top para alinhar o VS verticalmente com os scores
                                st.markdown("<p style='text-align: center; margin-top: 10px; font-weight: bold; color: red;'>VS</p>", 
                                            unsafe_allow_html=True)

                            # Força o alinhamento do score do Perdedor no centro da sua coluna
                            with col_score_l:
                                st.markdown(f"<h3 style='text-align: center; font-size: 24px;'>{loser_pts}</h3>", 
                                            unsafe_allow_html=True)
                            
                        # 3. Info Perdedor
                        with col_l_info:
                            st.image(get_logo_url(loser_abbr), width=50)
                            st.markdown(f"{loser_abbr}")
                        
                        # Linha de status
                        st.divider()
                        st.markdown(":heavy_check_mark: **FINALIZADO**")


# --- CARREGAMENTO GLOBAL DE DADOS ---

# 1. Tenta carregar os dados
historical_data = load_historical_events_from_nflverse(CURRENT_PFR_YEAR)
current_week_espn, live_events = load_live_events_from_espn()

# --- APLICAÇÃO PRINCIPAL (EXECUÇÃO) ---

# Usando colunas para centralizar o conteúdo principal no layout 'wide'
col_left, col_center, col_right = st.columns([1, 4, 1]) 

with col_center:
    st.title(f"🏈 :blue[Dashboard Histórico NFL] {CURRENT_PFR_YEAR}")
    st.markdown(f"Resultado e Classificação da Temporada Regular **{CURRENT_PFR_YEAR}**.")
    st.markdown("---") # Separador estético

    if historical_data.empty:
        st.error("O processamento não retornou dados. Verifique as mensagens de erro/aviso acima.")
    else:
        # 2. Exibe o placar
        display_scoreboard(historical_data, current_week_espn)
        
        st.divider()
        
        # 3. Calcula e exibe a classificação
        standings_data = calculate_standings(historical_data)

        st.header("🏆 Classificação da Temporada")
        st.info("Veja a situação atual das conferências por divisão. As cores do título (azul/vermelho) ajudam a identificar as conferências.")
        
        # Exibe em colunas (lado a lado) a classificação
        col_afc, col_nfc = st.columns([1, 1])
        
        with col_afc:
            display_standings(standings_data, 'AFC')
        
        with col_nfc:
            display_standings(standings_data, 'NFC')


        # 4. Filtro de semana (também centralizado)
        st.header("Explorar Outras Semanas")
        st.markdown("Visualize os resultados detalhados de qualquer semana já jogada.")
        st.text("") 

        all_weeks = sorted(historical_data['Week'].unique())
        
        default_index = len(all_weeks) - 1
        # Tenta usar a semana atual da ESPN como padrão, senão a última jogada.
        if current_week_espn is not None and current_week_espn in all_weeks: 
            default_index = all_weeks.index(current_week_espn)
        elif all_weeks:
             default_index = all_weeks.index(all_weeks[-1]) 


        selected_week = st.selectbox(
            'Selecione a Semana para Visualizar os Resultados:',
            options=all_weeks,
            index=default_index,
            key='week_selector' 
        )

        if selected_week is not None:
            df_selected_week = historical_data[historical_data['Week'] == selected_week].copy()
            
            if not df_selected_week.empty:
                st.subheader(f"Resultados Detalhados da Semana :red[{selected_week}] ({CURRENT_PFR_YEAR})")
                
                # A formatação de texto está correta agora (sem os códigos de cor literais)
                df_selected_week['Placar Final'] = df_selected_week.apply(
                    lambda row: f"**{row['Winner_PFR']}** ({int(row['Winner_Pts'])}) venceu {row['Loser_PFR']} ({int(row['Loser_Pts'])})", 
                    axis=1
                )
                
                df_final_view = df_selected_week[[
                    'Date_Full', 
                    'Placar Final',
                ]].rename(columns={'Date_Full': 'Data'})
                
                # Exibição tabular detalhada
                st.dataframe(
                    df_final_view, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "Data": "Data do Jogo",
                        "Placar Final": "Resultado",
                    }
                )
            else:
                st.info(f"Nenhum jogo finalizado encontrado na base histórica para a Semana {selected_week}.")
