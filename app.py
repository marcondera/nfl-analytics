import streamlit as st
import pandas as pd
import json
from datetime import datetime
import requests 
from dateutil.parser import isoparse 

# Configuração da página
st.set_page_config(
    page_title="NFL Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed" 
)

# --- 1. CONFIGURAÇÃO DE LOGOS E API ---

# A URL da API permanece a mesma, focada nos eventos de 2025
API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# Mapeamento para garantir que abreviações sejam traduzidas corretamente para a URL do logo
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin", 
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "det": "det", "GB": "gb", 
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar", 
    "LV": "rai", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg", 
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "tb": "tb", "TEN": "ten", 
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh", "TB": "tb", "DET": "det" 
}

def get_logo_url(abbreviation):
    """Gera a URL do logo (500x500) para melhor resolução, ajustada via HTML."""
    abbr = LOGO_MAP.get(abbreviation.upper(), abbreviation.lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"


# --- 2. FUNÇÕES DE PROCESSAMENTO DE DADOS ---

def get_period_name(period):
    """Mapeia o número do período para o nome do Quarto/Overtime."""
    if period == 1: return "1st Quarter"
    if period == 2: return "2nd Quarter"
    if period == 3: return "3rd Quarter"
    if period == 4: return "4th Quarter"
    if period > 4: return "OT"
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

    except Exception as e:
        # print(f"Erro ao processar evento: {e}") # Para debug
        return {
            'Jogo': 'Erro de Estrutura de Dados', 'Data': 'N/A',
            'Status': 'ERRO', 'Casa': 'ERRO', 'Visitante': 'ERRO',
            'Vencedor': 'N/A', 'Score Casa': 'N/A', 'Score Visitante': 'N/A',
            'Detalhe Status': 'Falha na extração',
        }


def load_data(api_url=API_URL_EVENTS_2025):
    """Busca dados EXCLUSIVAMENTE na API."""
    try:
        # Tenta buscar os dados da API
        response = requests.get(api_url)
        # Levanta uma exceção para códigos de status HTTP ruins (4xx ou 5xx)
        response.raise_for_status() 
        data = response.json()
    except requests.exceptions.RequestException as e:
        # Exibe erro no Streamlit se a chamada de rede falhar
        st.error(f"❌ Erro ao buscar dados da API. Verifique a URL ou a conexão de rede: {e}")
        return pd.DataFrame()
    except json.JSONDecodeError as e:
        # Exibe erro se o retorno da API não for um JSON válido
        st.error(f"❌ Erro ao decodificar JSON da API: {e}")
        return pd.DataFrame()

    events_list = data.get('events', [])
    events_data = [get_event_data(e) for e in events_list]
    # Remove qualquer entrada que tenha falhado na extração (retornou None ou a estrutura de ERRO)
    events_data = [item for item in events_data if item is not None and item['Status'] != 'ERRO']

    if not events_data:
        st.warning("A API retornou dados, mas a lista de eventos está vazia ou todos os eventos falharam na extração.")
        return pd.DataFrame()

    df = pd.DataFrame(events_data)
    return df

# --- 3. FUNÇÕES DE RENDERIZAÇÃO CUSTOMIZADA ---

def display_final_results_styled(df_finalized):
    """
    Renderiza os resultados em layout 3x1 (Ao Vivo, Finalizados, Agendados).
    Layout compacto, sem a tag "nfl-card" e sem a tag "game-container".
    Os estilos de card são aplicados ao container nativo do Streamlit.
    """

    rows = [row for index, row in df_finalized.iterrows()]

    # CSS com ajustes para layout mais compacto, SEM AS CLASSES CUSTOMIZADAS DE CONTAINER
    st.markdown("""
        <style>
            .stApp {
                background-color: #0E1117; 
            }
            
            /* Novo seletor para aplicar o estilo de "card" ao bloco de conteúdo DENTRO da coluna */
            /* Isso substitui a necessidade da div <div class="game-container"> */
            /* Nota: o seletor exato pode variar ligeiramente em versões futuras do Streamlit */
            [data-testid="stVerticalBlock"] > div {
                background-color: #282A36 !important; 
                border-radius: 12px !important; 
                padding: 12px 15px !important; 
                margin: 5px 0 !important; /* Espaçamento entre os cards */
                box-shadow: 0 2px 5px rgba(0,0,0,0.4) !important;
                color: #FAFAFA !important;
            }

            /* Forçar o style do Streamlit a aceitar a estilização do padding em colunas */
            .st-emotion-cache-1kyxisp, .st-emotion-cache-1r6ps53 {
                padding-left: 0.5rem;
                padding-right: 0.5rem;
            }

            .nfl-date-status {
                font-size: 11px;
                color: #B0B0B0; 
                text-align: center;
                margin-bottom: 8px !important;
                border-bottom: 1px solid #333;
                padding-bottom: 5px;
            }
            .nfl-team-block {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
            }
            .nfl-team-info {
                display: flex;
                align-items: center;
                margin-right: 15px; 
                max-width: 180px; 
            }
            .nfl-score {
                font-size: 20px; 
                font-weight: 500;
                color: #888888; 
                text-align: right;
            }
            .nfl-score-winner {
                font-size: 24px; 
                font-weight: 900; 
                color: #69be28; 
                text-align: right;
            }
            .nfl-abbr {
                font-size: 16px; 
                font-weight: 700;
                color: #FAFAFA;
                margin-left: 10px;
                white-space: nowrap;
                overflow: hidden;
            }
            .nfl-footer {
                font-size: 10px;
                color: #B0B0B0;
                text-align: center;
                margin-top: 5px;
            }
        </style>
    """, unsafe_allow_html=True)

    # Processa em grupos de 3 para o layout de colunas
    for i in range(0, len(rows), 3):

        cols = st.columns(3, gap="small")
        chunk = rows[i:i+3]

        for j, row in enumerate(chunk):
            with cols[j]:

                is_home_winner = row['Vencedor'] == row['Casa']
                is_away_winner = row['Vencedor'] == row['Visitante']

                # Definir Status do Detalhe
                if row['Status'] == 'Agendado':
                    status_display = f'⏰ {row["Data"]} | {row["Detalhe Status"]}'
                elif row['Status'] == 'Em Andamento':
                    status_display = f'🔴 AO VIVO | {row["Detalhe Status"]}'
                else: # Finalizado
                    status_display = f'✅ {row["Detalhe Status"]}'


                # --- O CONTEÚDO AGORA ESTÁ DIRETAMENTE NA COLUNA, SEM O WRAPPER game-container ---

                # 1. Data/Status
                st.markdown(f'<p class="nfl-date-status">{status_display}</p>', unsafe_allow_html=True)

                # 2. Time Visitante
                away_score_class = "nfl-score-winner" if is_away_winner else "nfl-score"
                score_away = row["Score Visitante"] if row['Status'] != 'Agendado' else '-'
                
                st.markdown(
                    f"""
                    <div class="nfl-team-block">
                        <div class="nfl-team-info">
                            <img src="{get_logo_url(row['Visitante'])}" width="30" height="30" style="margin-right: 5px;">
                            <span class="nfl-abbr">{row['Visitante']}</span>
                        </div>
                        <span class="{away_score_class}">{score_away}</span>
                    </div>
                    """, unsafe_allow_html=True
                )

                # 3. Time Casa
                home_score_class = "nfl-score-winner" if is_home_winner else "nfl-score"
                score_home = row["Score Casa"] if row['Status'] != 'Agendado' else '-'

                st.markdown(
                    f"""
                    <div class="nfl-team-block">
                        <div class="nfl-team-info">
                            <img src="{get_logo_url(row['Casa'])}" width="30" height="30" style="margin-right: 5px;">
                            <span class="nfl-abbr">{row['Casa']}</span>
                        </div>
                        <span class="{home_score_class}">{score_home}</span>
                    </div>
                    """, unsafe_allow_html=True
                )

                # 4. Rodapé (Nome Completo do Jogo)
                st.markdown(f'<p class="nfl-footer">{row["Jogo"]}</p>', unsafe_allow_html=True)

                # FIM DO CONTEÚDO

def display_season_history_table(df_history):
    """
    Renderiza a tabela completa e estilizada dos jogos finalizados da temporada.
    """
    # 1. Seleciona e Renomeia colunas para PT-BR
    df_table = df_history[
        ['Data', 'Casa', 'Score Casa', 'Visitante', 'Score Visitante', 'Vencedor', 'Detalhe Status', 'Jogo']
    ].rename(columns={
        'Score Casa': 'Placar Casa',
        'Score Visitante': 'Placar Fora',
        'Detalhe Status': 'Status',
        'Visitante': 'Time Visitante',
        'Casa': 'Time Casa'
    })

    # 2. Renderiza a tabela com o Streamlit, configurando as colunas
    st.dataframe(
        df_table, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "Data": st.column_config.TextColumn("Data", width="small"),
            "Time Casa": st.column_config.TextColumn("Time Casa", width="small"),
            "Placar Casa": st.column_config.NumberColumn("Placar Casa", format="%d", width="small"),
            "Time Visitante": st.column_config.TextColumn("Time Visitante", width="small"),
            "Placar Fora": st.column_config.NumberColumn("Placar Fora", format="%d", width="small"),
            "Vencedor": st.column_config.TextColumn("Vencedor", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Jogo": st.column_config.TextColumn("Jogo", width="large") # Jogo completo
        }
    )

# --- 4. LAYOUT DO DASHBOARD STREAMLIT (MAIN) ---

def main():

    # Injeta CSS Global para o fundo e CENTRALIZAÇÃO DE TEXTOS
    st.markdown("""
        <style>
            /* Centraliza H1 (Título Principal) */
            h1 {
                text-align: center;
                padding-top: 0px !important;
                margin-top: 0px !important;
                margin-bottom: 1rem;
            }
            /* Centraliza H2 (Títulos das Seções) */
            h2 {
                text-align: center;
                margin-top: 1.5rem; 
                margin-bottom: 0.5rem; 
            }
            /* Ajusta padding superior do container principal do Streamlit */
            .css-1d3f0g2 { 
                padding-top: 1.5rem; 
            }
            /* Estilo para a linha divisória (---) */
            hr {
                margin-top: 2rem;
                margin-bottom: 2rem;
            }
        </style>
    """, unsafe_allow_html=True)

    st.title("🏈 Resultados da NFL")

    df_events = load_data() 

    if df_events.empty:
        st.error("Não foi possível carregar os dados. O dashboard não será exibido. Por favor, verifique as mensagens de erro acima.")
        return

    # --- JOGOS AO VIVO (EM ANDAMENTO) ---

    st.header("🔴 Ao Vivo")
    df_in_progress = df_events[df_events['Status'] == 'Em Andamento'].sort_values(by='Data', ascending=False)

    if not df_in_progress.empty:
        display_final_results_styled(df_in_progress)
    else:
        st.markdown('<p style="color:#888; text-align: center; margin-bottom: 1rem;">Nenhum jogo em andamento no momento.</p>', unsafe_allow_html=True)

    # SEPARADOR ENTRE AO VIVO E FINALIZADOS
    st.markdown("---")

    # --- RESULTADOS FINAIS (CARDS) ---

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
        display_final_results_styled(df_scheduled)
    else:
        st.markdown('<p style="color:#888; text-align: center; margin-bottom: 1rem;">Nenhum jogo agendado nos dados fornecidos.</p>', unsafe_allow_html=True)

    # SEPARADOR ENTRE AGENDADOS E HISTÓRICO COMPLETO
    st.markdown("---")

    # --- HISTÓRICO COMPLETO DA TEMPORADA (TABELA) ---
    st.header("📚 Histórico Completo da Temporada")

    if not df_finalized.empty:
        # Reutiliza o df_finalized (todos os jogos finalizados)
        display_season_history_table(df_finalized)
    else:
        st.markdown('<p style="color:#888; text-align: center;">Nenhum resultado finalizado no histórico para exibir.</p>', unsafe_allow_html=True)


if __name__ == '__main__':
    main()
