import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta
import json
import math
import re
import numpy as np

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="🏈 NFL Dashboard Histórico", layout="wide", page_icon="🏈")

# Constante: Ano para buscar dados históricos no PFR
CURRENT_PFR_YEAR = 2025 

# Endpoints
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
PFR_URL_TEMPLATE = f"https://www.pro-football-reference.com/years/{CURRENT_PFR_YEAR}/games.htm"

# Mapa de Logos e Abbr para PFR (necessário para mapear nomes do PFR para logos da ESPN)
LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

# Mapeamento de nomes completos/curtos do PFR para abreviações da ESPN (ajuste conforme necessário)
# Este é um mapeamento crucial para o scraping. PFR é a chave, ESPN é o valor.
PFR_ABBR_MAP = {
    '49ers': 'SF', 'Bills': 'BUF', 'Falcons': 'ATL', 'Ravens': 'BAL', 'Panthers': 'CAR', 'Bengals': 'CIN',
    'Bears': 'CHI', 'Browns': 'CLE', 'Cowboys': 'DAL', 'Broncos': 'DEN', 'Lions': 'DET', 'Packers': 'GB',
    'Texans': 'HOU', 'Colts': 'IND', 'Jaguars': 'JAX', 'Chiefs': 'KC', 'Chargers': 'LAC', 'Rams': 'LAR',
    'Raiders': 'LV', 'Dolphins': 'MIA', 'Vikings': 'MIN', 'Patriots': 'NE', 'Saints': 'NO', 'Giants': 'NYG',
    'Jets': 'NYJ', 'Eagles': 'PHI', 'Steelers': 'PIT', 'Seahawks': 'SEA', 'Buccaneers': 'TB', 'Titans': 'TEN',
    'Cardinals': 'ARI', 'Commanders': 'WSH',
    # PFR usa nomes completos ou abreviações inconsistentes, este mapeamento cobre o mais comum
    'San Francisco': 'SF', 'Buffalo': 'BUF', 'Atlanta': 'ATL', 'Baltimore': 'BAL', 'Carolina': 'CAR', 'Cincinnati': 'CIN',
    'Chicago': 'CHI', 'Cleveland': 'CLE', 'Dallas': 'DAL', 'Denver': 'DEN', 'Detroit': 'DET', 'Green Bay': 'GB',
    'Houston': 'HOU', 'Indianapolis': 'IND', 'Jacksonville': 'JAX', 'Kansas City': 'KC', 'Los Angeles Chargers': 'LAC', 'Los Angeles Rams': 'LAR',
    'Las Vegas': 'LV', 'Miami': 'MIA', 'Minnesota': 'MIN', 'New England': 'NE', 'New Orleans': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia': 'PHI', 'Pittsburgh': 'PIT', 'Seattle': 'SEA', 'Tampa Bay': 'TB', 'Tennessee': 'TEN',
    'Arizona': 'ARI', 'Washington': 'WSH'
}

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def normalize_team_name(name):
    """Converte o nome do time PFR em abreviação ESPN."""
    # Tenta mapear o nome completo ou partes dele
    for key, abbr in PFR_ABBR_MAP.items():
        if key in name:
            return abbr
    # Tenta usar a última palavra como abreviação curta (ex: Eagles -> PHI)
    last_word = name.split()[-1]
    for key, abbr in PFR_ABBR_MAP.items():
        if key == last_word:
            return abbr
    return name.upper() # Fallback

def get_period_name(period):
    period_map = {1: "1º Quarto", 2: "2º Quarto", 3: "3º Quarto", 4: "4º Quarto"}
    return period_map.get(period, "Prorrogação" if period > 4 else "")

# --- FUNÇÃO DE CARREGAMENTO HISTÓRICO (PFR) ---
@st.cache_data(ttl=60 * 60 * 24) # Cache PFR data por 1 dia
def load_historical_events_from_pfr(year):
    """
    Raspa o cronograma e resultados da temporada do Pro-Football-Reference.
    A lógica foi tornada mais robusta para identificar colunas mesmo que os nomes mudem.
    """
    url = f"https://www.pro-football-reference.com/years/{year}/games.htm"
    st.info(f"Carregando histórico e cronograma completo da temporada {year} de Pro-Football-Reference...")
    
    try:
        # PFR tem um comentário HTML com a tabela que precisamos
        html_content = requests.get(url, timeout=15).text
        
        # Encontra o conteúdo comentado da tabela
        match = re.search(r'<!--\s*<div class="table_container" id="div_games">.*?</table>\s*</div>\s*-->', html_content, re.DOTALL)
        
        if not match:
            # Caso a tabela não esteja comentada (versão mais antiga do PFR)
            df_list = pd.read_html(url)
            if not df_list:
                st.error("Não foi possível encontrar a tabela de jogos no PFR. Verifique o ano da temporada.")
                return pd.DataFrame()
            df = df_list[0]
        else:
             # Se a tabela estiver comentada, extrai e usa o conteúdo
            table_html = match.group(0).replace('<!--', '').replace('-->', '').strip()
            df = pd.read_html(table_html)[0]


        # 1. Achata os cabeçalhos de coluna (MultiIndex) para strings únicas.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(col).strip() for col in df.columns.values]
        else:
            df.columns = [col.strip() for col in df.columns]

        # 2. Mapeamento de colunas dinâmico (mais robusto)
        column_map = {}
        
        # Identifica a coluna 'Week' (Semana).
        # Procura por colunas que contenham 'Week' e geralmente 'Unnamed'
        original_week_col = next((c for c in df.columns if 'Week' in c and 'Unnamed' in c), None)
        if not original_week_col:
            # Fallback: procura apenas por 'Week'
            original_week_col = next((c for c in df.columns if 'Week' in c), None)
            
        if not original_week_col:
            st.error("Coluna 'Week' (Semana) não encontrada na tabela do PFR. O formato do site pode ter mudado drasticamente.")
            return []
            
        # Adiciona a Week ao mapeamento
        column_map[original_week_col] = 'Week'
            
        # Mapeamento das outras colunas essenciais, buscando o nome mais provável
        original_day_col = next((c for c in df.columns if 'Day' in c and 'Unnamed' in c), None)
        if original_day_col: column_map[original_day_col] = 'Day'
        
        original_date_col = next((c for c in df.columns if 'Date' in c and 'Unnamed' in c), None)
        if original_date_col: column_map[original_date_col] = 'Date'

        original_winner_col = next((c for c in df.columns if 'Winner' in c and 'tie' in c), None)
        if original_winner_col: column_map[original_winner_col] = 'Winner'

        original_loser_col = next((c for c in df.columns if 'Loser' in c and 'tie' in c), None)
        if original_loser_col: column_map[original_loser_col] = 'Loser'
        
        original_pts_w_col = next((c for c in df.columns if 'PtsW' in c), None)
        if original_pts_w_col: column_map[original_pts_w_col] = 'PtsW'
        
        original_pts_l_col = next((c for c in df.columns if 'PtsL' in c), None)
        if original_pts_l_col: column_map[original_pts_l_col] = 'PtsL'
        
        # Renomeia o DataFrame
        df = df.rename(columns=column_map)

        # Verificação final da Week (deve existir após o mapeamento)
        if 'Week' not in df.columns:
            st.error("Falha ao renomear a coluna da semana. O formato do PFR pode ter mudado.")
            return []
            
        # Limpeza e filtragem
        # Filtra linhas onde 'Week' não é um número (remove cabeçalhos repetidos e linhas vazias)
        df = df.dropna(subset=['Week']).copy()
        
        # Converte a coluna 'Week' para string para poder filtrar o cabeçalho 'Week'
        df['Week_str'] = df['Week'].astype(str).str.strip()
        df = df[df['Week_str'] != 'Week'].copy()
        df = df.drop(columns=['Week_str'])
        
        # Conversão para lista de eventos (estrutura parecida com a da ESPN)
        games_list = []
        for index, row in df.iterrows():
            
            # Limpa o campo de vencedor para identificar o time da casa/fora e a abreviação
            winner_name = str(row['Winner']).replace('@', '').strip()
            loser_name = str(row['Loser']).replace('@', '').strip()
            
            # PFR usa '@' para indicar que o vencedor estava jogando FORA
            # Se o vencedor tem '@', ele é o time AWAY. O perdedor é o HOME.
            is_winner_away = str(row['Winner']).strip().endswith('@')
            
            # Se o jogo ainda não ocorreu, PFR usa 'nan' nos campos de pontuação/vencedor
            is_finalized = not pd.isna(row['PtsW']) and not pd.isna(row['PtsL'])
            
            try:
                week_num = int(row['Week'])
            except ValueError:
                continue # Pula se a semana não for um número válido (ex: cabeçalho)
            
            if is_finalized:
                # O PFR usa a coluna 'Loser' para quem perdeu e 'Winner' para quem ganhou.
                # Se o vencedor tem '@', ele jogou fora (AWAY). O perdedor é o HOME.
                if is_winner_away:
                    away_abbr = normalize_team_name(winner_name)
                    home_abbr = normalize_team_name(loser_name)
                    away_score = int(row['PtsW'])
                    home_score = int(row['PtsL'])
                else:
                    # Se o vencedor não tem '@', ele jogou em casa (HOME). O perdedor é o AWAY.
                    home_abbr = normalize_team_name(winner_name)
                    away_abbr = normalize_team_name(loser_name)
                    home_score = int(row['PtsW'])
                    away_score = int(row['PtsL'])
                
                status_pt = "Finalizado"
                winner = home_abbr if home_score > away_score else away_abbr
            else:
                # Jogo não finalizado (programado).
                
                # Invertendo a lógica: o time com '@' na coluna Loser é o time de FORA (Away).
                # O outro time é o time da CASA (Home).
                if '@' in str(row['Loser']):
                    away_abbr = normalize_team_name(loser_name)
                    home_abbr = normalize_team_name(winner_name)
                elif '@' in str(row['Winner']): # Pouco comum, mas verifica
                    away_abbr = normalize_team_name(winner_name)
                    home_abbr = normalize_team_name(loser_name)
                else:
                     # Se não há '@', PFR geralmente lista o time HOME primeiro. (Winner é Home)
                    home_abbr = normalize_team_name(winner_name)
                    away_abbr = normalize_team_name(loser_name)


                status_pt = "Agendado"
                home_score = 0
                away_score = 0
                winner = "N/A"

            # Formato de data e timestamp (o PFR só dá a data, não a hora)
            try:
                date_str = f"{row['Date']} {year}"
                date_obj = datetime.strptime(date_str, '%B %d %Y')
                date_formatada = date_obj.strftime('%d/%m/%Y 00:00') # Placeholder time
                timestamp_iso = date_obj.isoformat()
            except:
                date_formatada = "N/A"
                timestamp_iso = ""

            games_list.append({
                'id': f"PFR-{year}-{week_num}-{home_abbr}-{away_abbr}",
                'name': f"{away_abbr} @ {home_abbr}",
                'week': week_num,
                'date': date_formatada,
                'timestamp': timestamp_iso,
                'status': status_pt,
                'home': home_abbr,
                'away': away_abbr,
                'home_score': home_score,
                'away_score': away_score,
                'winner': winner,
                'home_logo': get_logo_url(home_abbr),
                'away_logo': get_logo_url(away_abbr)
            })
            
        return games_list
    
    except Exception as e:
        # Imprime o erro original para debug
        st.error(f"Erro carregando eventos históricos do PFR: {e}. Verifique o formato da tabela do PFR.")
        return []

def parse_event_from_scoreboard(evt):
    # Sua função original (simplificada para não repetir)
    try:
        comp = evt.get('competitions', [])[0]
        date_iso = comp.get('date')
        data_obj = isoparse(date_iso) if date_iso else None
        data_formatada = data_obj.strftime('%d/%m/%Y %H:%M') if data_obj else "N/A"
        status_obj = comp.get('status', {})
        stype = status_obj.get('type', {}) or {}
        stype_state = stype.get('state')
        status_pt = ""
        if stype_state == 'in':
            clock = status_obj.get('displayClock', '')
            period = status_obj.get('period', 0)
            status_pt = f"Em Andamento – {clock} no {get_period_name(period)}"
        elif stype_state == 'post':
            status_pt = "Finalizado"
        else:
            status_pt = "Agendado"

        competitors = comp.get('competitors', [])
        home = next((c for c in competitors if c.get('homeAway') == 'home'), None)
        away = next((c for c in competitors if c.get('homeAway') == 'away'), None)

        home_abbr = home.get('team', {}).get('abbreviation', 'CASA') if home else "CASA"
        away_abbr = away.get('team', {}).get('abbreviation', 'FORA') if away else "FORA"
        home_score = int(home.get('score', 0)) if home and home.get('score') is not None else 0
        away_score = int(away.get('score', 0)) if away and away.get('score') is not None else 0
        
        winner = home_abbr if home_score > away_score else (away_abbr if away_score > home_score else "Empate")

        return {
            'id': evt.get('id'),
            'date': data_formatada,
            'status': status_pt,
            'home': home_abbr,
            'away': away_abbr,
            'home_score': home_score,
            'away_score': away_score,
            'winner': winner,
            'timestamp': data_obj.isoformat() if data_obj else "",
        }
    except Exception:
        return None

# Função auxiliar para carregar dados atuais (não foi alterada, mantida por completude)
def load_current_events_from_espn():
    """Carrega dados em tempo real da ESPN e retorna um dicionário mapeado pela chave Away@Home."""
    try:
        response = requests.get(API_URL_SCOREBOARD, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Mapeia eventos para a chave "Away@Home"
        events_map = {}
        for event in data.get('events', []):
            parsed_event = parse_event_from_scoreboard(event)
            if parsed_event:
                key = f"{parsed_event['away']}@{parsed_event['home']}"
                events_map[key] = parsed_event
        return events_map
    except Exception as e:
        st.error(f"Erro ao carregar dados em tempo real da ESPN: {e}")
        return {}


# --- LÓGICA DE COMBINAÇÃO E EXIBIÇÃO ---
st.markdown(f"<h1>🏈 NFL Dashboard ({CURRENT_PFR_YEAR})</h1>", unsafe_allow_html=True)
st.caption(f"Dados históricos/cronograma de **Pro-Football-Reference ({CURRENT_PFR_YEAR})** combinados com dados em tempo real da **ESPN Scoreboard**.")

if st.button("🔄 Atualizar"):
    st.cache_data.clear()
    st.rerun()

# 1. Carrega dados históricos (full season)
pfr_events = load_historical_events_from_pfr(CURRENT_PFR_YEAR)
if not pfr_events:
    st.stop()

# 2. Carrega dados em tempo real da ESPN (para jogos em andamento/recentes)
espn_updates = load_current_events_from_espn()

# 3. Combina/Sobrepõe dados
final_events = []
for pfr_game in pfr_events:
    # Cria uma chave de busca simples para mapeamento
    match_key = f"{pfr_game['away']}@{pfr_game['home']}"
    
    if match_key in espn_updates:
        # Se o jogo estiver na ESPN, pega o status e o placar atualizado
        espn_game = espn_updates[match_key]
        
        # Só atualiza o placar/status se o jogo da ESPN estiver 'in' ou 'post'
        if espn_game['status'] != 'Agendado':
            pfr_game['status'] = espn_game['status']
            pfr_game['home_score'] = espn_game['home_score']
            pfr_game['away_score'] = espn_game['away_score']
            pfr_game['winner'] = espn_game['winner']
            # Mantém a data/hora da ESPN se for mais precisa
            pfr_game['date'] = espn_game['date']
            pfr_game['timestamp'] = espn_game['timestamp']
            
    final_events.append(pfr_game)

# 4. Processa e exibe as categorias
in_progress = [e for e in final_events if "Em Andamento" in e['status']]
scheduled = [e for e in final_events if "Agendado" in e['status']]
finalized = [e for e in final_events if e not in in_progress and e not in scheduled]

# Agrupa por semana (agora usa o campo 'week' do PFR)
weeks = {}
for e in final_events:
    wk = e.get('week', 0)
    if wk >= 1:
        weeks.setdefault(wk, []).append(e)

# Geração de estatísticas (usa a mesma lógica de antes)
def compute_standings(finalized_games):
    stats = {}
    for g in finalized_games:
        h = g['home']; a = g['away']
        hs = g['home_score']; as_ = g['away_score']
        for t in (h,a):
            stats.setdefault(t, {'team':t, 'W':0, 'L':0, 'T':0, 'PF':0, 'PA':0, 'games':[]})
        
        # Ignora times que não foram mapeados corretamente (fallback)
        if h in stats and a in stats:
            stats[h]['PF'] += hs
            stats[h]['PA'] += as_
            stats[a]['PF'] += as_
            stats[a]['PA'] += hs
            if hs > as_:
                stats[h]['W'] += 1
                stats[a]['L'] += 1
                stats[h]['games'].append('W')
                stats[a]['games'].append('L')
            elif as_ > hs:
                stats[a]['W'] += 1
                stats[h]['L'] += 1
                stats[a]['games'].append('W')
                stats[h]['games'].append('L')
            else:
                stats[h]['T'] += 1
                stats[a]['T'] += 1
                stats[h]['games'].append('T')
                stats[a]['games'].append('T')
                
    rows = []
    for t, s in stats.items():
        gp = s['W'] + s['L'] + s['T']
        wpct = (s['W'] + 0.5*s['T']) / gp if gp > 0 else 0
        
        streak = ""
        if s['games']:
            rev = s['games'][::-1]
            cur = rev[0]
            cnt = 1
            for x in rev[1:]:
                if x == cur:
                    cnt += 1
                else:
                    break
            streak = f"{cur}{cnt}"
            
        rows.append({
            'Team': t, 'W': s['W'], 'L': s['L'], 'T': s['T'],
            'PF': s['PF'], 'PA': s['PA'], 'Win%': round(wpct,3), 'Streak': streak
        })
    rows.sort(key=lambda x: (x['Win%'], x['PF'] - x['PA']), reverse=True)
    return rows

standings = compute_standings(finalized)

# blowouts (maiores margens)
def biggest_blowouts(finalized_games, top_n=5):
    arr = []
    for g in finalized_games:
        diff = abs(g['home_score'] - g['away_score'])
        arr.append((diff, g))
    arr.sort(reverse=True, key=lambda x: x[0])
    return [x[1] for x in arr[:top_n]]

blowouts = biggest_blowouts(finalized, top_n=5)

# preparar payload
payload = {
    "sections": [
        {"title": "🔴 Jogos Ao Vivo", "games": in_progress},
        {"title": "⏳ Próximos Jogos", "games": scheduled},
        {"title": "✅ Resultados Históricos", "games": finalized}
    ],
    "weeks": weeks,
    "standings": standings,
    "blowouts": blowouts
}

payload_json = json.dumps(payload)

# HTML frontend embutido
html_template = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>
:root{
    --bg:#0e1117; --card:#1a1f25; --muted:#8f99a6; --accent:#4CAF50; --danger:#FF4B4B;
}
body { background:var(--bg); color:#fff; font-family:Inter, sans-serif; margin:0; padding:0; overflow-x:hidden; }
.wrap { max-width:1200px; margin:auto; padding:16px; }
.section { margin-bottom:40px; }
.section h2 { font-size:1.25rem; color:#e6eef8; border-left:4px solid var(--accent); padding-left:8px; margin-bottom:16px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px,1fr)); gap:20px; }
.card { background:var(--card); border-radius:12px; padding:16px; display:flex; flex-direction:column; align-items:center; transition: transform 0.2s ease; }
.card:hover { transform: translateY(-3px); }
.meta { font-size:0.85rem; color:var(--muted); margin-bottom:8px; }
.teams { display:flex; align-items:center; justify-content:center; gap:12px; width:100%; }
.team { display:flex; flex-direction:column; align-items:center; }
.logo { width:56px; height:56px; border-radius:10px; background:#fff; overflow:hidden; display:flex; align-items:center; justify-content:center; }
.logo img { width:100%; height:100%; object-fit:contain; padding: 4px; box-sizing: border-box;} 
.score { font-size:2.4rem; font-weight:800; white-space:nowrap; margin:0 8px; }
.team-name { font-weight:600; max-width: 65px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.status { font-size:0.9rem; color:var(--muted); margin-top:8px; text-align:center; }
.details { background:var(--card); border-radius:10px; padding:12px; }
.week-block { margin-bottom:12px; }
.small { font-size:0.85rem; color:var(--muted); }
.table { width:100%; border-collapse:collapse; margin-top:12px; }
.table th, .table td { border-bottom:1px solid rgba(255,255,255,0.08); padding:8px 6px; text-align:center; }
.table th { color:var(--muted); font-weight:700; }
.winner-text { color:var(--accent); font-weight:800; }
.loser-text { color:var(--danger); font-weight:700; }
.winner-score { color: var(--accent); }
.loser-score { color: #e6eef8; }
@media(max-width:600px){ 
    .score { font-size:1.8rem; } 
    .logo { width:48px; height:48px; } 
    .team-name { max-width: 50px; }
}
</style>
</head>
<body>
<div class="wrap" id="root"></div>
<script>
const payload = PAYLOAD_JSON;
const root = document.getElementById('root');

// render sections
payload.sections.forEach(sec=>{
    if(!sec.games || sec.games.length===0) return;
    const secDiv = document.createElement('div');
    secDiv.className = 'section';
    const h2 = document.createElement('h2');
    h2.textContent = sec.title;
    secDiv.appendChild(h2);
    const grid = document.createElement('div');
    grid.className = 'grid';
    sec.games.forEach(g=>{
        const card = document.createElement('div');
        card.className = 'card';
        const homeClass = (g.winner === g.home && g.status === 'Finalizado') ? 'winner-text' : '';
        const awayClass = (g.winner === g.away && g.status === 'Finalizado') ? 'winner-text' : '';
        
        let homeScoreClass = '';
        let awayScoreClass = '';

        if (g.status === 'Finalizado' && g.winner !== 'Empate') {
            homeScoreClass = g.winner === g.home ? 'winner-score' : 'loser-score';
            awayScoreClass = g.winner === g.away ? 'winner-score' : 'loser-score';
        }

        // Se o jogo está agendado, a pontuação é 0, removemos as classes de score
        if (g.status === 'Agendado' || g.status === 'Em Andamento') {
             homeScoreClass = '';
             awayScoreClass = '';
        }

        card.innerHTML = `
            <div class="meta">Semana ${g.week} | ${g.date}</div>
            <div class="teams">
                <div class="team"><div class="logo"><img src="${g.home_logo}"></div><div class="team-name ${homeClass}">${g.home}</div></div>
                <div class="score">
                    <span class="${homeScoreClass}">${g.home_score}</span> - <span class="${awayScoreClass}">${g.away_score}</span>
                </div>
                <div class="team"><div class="logo"><img src="${g.away_logo}"></div><div class="team-name ${awayClass}">${g.away}</div></div>
            </div>
            <div class="status">${g.status}</div>`;
        grid.appendChild(card);
    });
    secDiv.appendChild(grid);
    root.appendChild(secDiv);
});

// weekly history collapsible
const weeksRoot = document.createElement('div');
const wSec = document.createElement('div');
wSec.className = 'section';
const wh = document.createElement('h2');
wh.textContent = '📜 Histórico por Semana';
wSec.appendChild(wh);

Object.keys(payload.weeks).map(Number).sort((a,b)=>a-b).forEach(k=>{
    const arr = payload.weeks[k];
    if(!arr || arr.length===0) return;
    
    // Filtra jogos agendados para a semana para focar no histórico/resultados
    const finalizedGames = arr.filter(g => g.status === 'Finalizado');
    if (finalizedGames.length === 0 && k < payload.weeks[Object.keys(payload.weeks).length].week) return; // Oculta semanas vazias no passado

    const block = document.createElement('div');
    block.className = 'week-block';
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.innerHTML = `Semana ${k} <span class="small">(${arr.length} jogos, ${finalizedGames.length} finalizados)</span>`;
    details.appendChild(summary);
    const inner = document.createElement('div');
    inner.className = 'details small';
    
    // Ordena os jogos por status (Finalizado > Em Andamento > Agendado)
    arr.sort((a, b) => {
        const statusOrder = { 'Em Andamento': 3, 'Finalizado': 2, 'Agendado': 1 };
        return statusOrder[b.status] - statusOrder[a.status];
    });

    arr.forEach(g=>{
        const homeClass = (g.winner === g.home && g.status === 'Finalizado') ? 'winner-text' : '';
        const awayClass = (g.winner === g.away && g.status === 'Finalizado') ? 'winner-text' : '';
        const line = document.createElement('p');
        
        let scoreDisplay = `${g.home_score} - ${g.away_score}`;
        if (g.status === 'Agendado') {
             scoreDisplay = '-';
        }
        
        line.innerHTML = `<span>${g.date}</span> — <span class="${homeClass}">${g.home}</span> ${scoreDisplay} <span class="${awayClass}">${g.away}</span> <span class="small">· ${g.status}</span>`;
        inner.appendChild(line);
    });
    details.appendChild(inner);
    block.appendChild(details);
    wSec.appendChild(block);
});
root.appendChild(wSec);

// standings
const stSec = document.createElement('div');
stSec.className = 'section';
const sth2 = document.createElement('h2');
sth2.textContent = '🏆 Classificação (Geral)';
stSec.appendChild(sth2);
const stDiv = document.createElement('div');
stDiv.className = 'details';
if(payload.standings.length > 0){
    const t = document.createElement('table');
    t.className = 'table';
    t.innerHTML = `<thead><tr><th>Pos</th><th>Time</th><th>W</th><th>L</th><th>T</th><th>PF</th><th>PA</th><th>Win%</th><th>Streak</th></tr></thead>`;
    const tb = document.createElement('tbody');
    payload.standings.forEach((r,i)=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${i+1}</td><td>${r.Team}</td><td>${r.W}</td><td>${r.L}</td><td>${r.T}</td><td>${r.PF}</td><td>${r.PA}</td><td>${r['Win%'].toFixed(3)}</td><td>${r.Streak}</td>`;
        tb.appendChild(tr);
    });
    t.appendChild(tb);
    stDiv.appendChild(t);
} else {
    stDiv.innerHTML = "<div class='small'>Sem dados de jogos finalizados.</div>";
}
stSec.appendChild(stDiv);
root.appendChild(stSec);

// blowouts
const boSec = document.createElement('div');
boSec.className = 'section';
const boh = document.createElement('h2');
boh.textContent = '💥 Maiores Vitórias';
boSec.appendChild(boh);
const boDiv = document.createElement('div');
boDiv.className = 'details';
if(payload.blowouts.length > 0){
    payload.blowouts.forEach(g=>{
        const diff = Math.abs(g.home_score - g.away_score);
        const winner = g.home_score > g.away_score ? g.home : (g.away_score > g.home_score ? g.away : '');
        const winnerHomeScoreClass = (g.home_score > g.away_score) ? 'winner-text' : '';
        const winnerAwayScoreClass = (g.away_score > g.home_score) ? 'winner-text' : '';
    
        const p = document.createElement('p');
        p.innerHTML = `<span>Semana ${g.week} | ${g.date}</span> — <span class="${winner===g.home?'winner-text':''}">${g.home}</span> <span class="${winnerHomeScoreClass}">${g.home_score}</span> - <span class="${winnerAwayScoreClass}">${g.away_score}</span> <span class="${winner===g.away?'winner-text':''}">${g.away}</span> <span class="small">· dif ${diff}</span>`;
        boDiv.appendChild(p);
    });
} else {
    boDiv.innerHTML = "<div class='small'>Sem jogos finalizados.</div>";
}
boSec.appendChild(boDiv);
root.appendChild(boSec);

</script>
</body>
</html>
"""

html_code = html_template.replace("PAYLOAD_JSON", json.dumps(payload))

# cálculo de altura para evitar corte
num = len(final_events)
rows = math.ceil(num / 3)
# Aumentei o limite máximo de altura para garantir que todo o conteúdo seja exibido.
# E mudei scrolling para True.
height = min(800 + rows * 120, 15000)

st.download_button("📥 Baixar histórico CSV", data=pd.DataFrame(final_events).to_csv(index=False).encode('utf-8'),
                   file_name="nfl_full_season_history.csv", mime="text/csv")

st.components.v1.html(html_code, height=height, scrolling=True)
