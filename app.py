import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta, date
import json
import math

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="🏈 NFL Dashboard", layout="wide", page_icon="🏈")

API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
API_URL_EVENTS = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "WAS": "wsh", "ARI": "ari", "WSH": "wsh"
}

def get_logo_url(abbreviation):
    abbr = LOGO_MAP.get(str(abbreviation).upper(), str(abbreviation).lower())
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr}.png"

def get_period_name(period):
    period_map = {1: "1º Quarto", 2: "2º Quarto", 3: "3º Quarto", 4: "4º Quarto"}
    return period_map.get(period, "Prorrogação" if period > 4 else "")

def parse_event_from_scoreboard(evt):
    """
    Dado um evento no formato da resposta do scoreboard ou evento detalhado,
    extrai os campos que interessam para nosso dashboard.
    """
    try:
        comp = evt.get('competitions', [])[0] if evt.get('competitions') else evt
        # data
        date_iso = comp.get('date')
        data_obj = isoparse(date_iso) if date_iso else None
        data_formatada = data_obj.strftime('%d/%m/%Y %H:%M') if data_obj else "N/A"
        # status
        status_obj = comp.get('status', {})
        stype = status_obj.get('type') or {}
        stype_state = stype.get('state')
        # status em pt
        status_pt = ""
        if stype_state == 'in':
            clock = status_obj.get('displayClock', '')
            period = status_obj.get('period', 0)
            status_pt = f"Em Andamento – {clock} no {get_period_name(period)}"
        elif stype_state == 'pre':
            status_pt = "Agendado"
        elif stype_state == 'post':
            status_pt = "Finalizado"
        else:
            status_pt = stype.get('description', "Finalizado")
        # times e pontuações
        competitors = comp.get('competitors', [])
        home = None; away = None
        for c in competitors:
            if c.get('homeAway') == 'home':
                home = c
            elif c.get('homeAway') == 'away':
                away = c
        if home is None and len(competitors) > 0:
            home = competitors[0]
        if away is None and len(competitors) > 1:
            # se primeiro já é home, pega o segundo; senão, pega o outro
            if home and home.get('homeAway') == 'home' and competitors[1].get('homeAway') != 'home':
                away = competitors[1]
            elif not home:
                away = competitors[1]
        home_abbr = home.get('team', {}).get('abbreviation', 'CASA') if home else "CASA"
        away_abbr = away.get('team', {}).get('abbreviation', 'FORA') if away else "FORA"
        home_score = int(home.get('score', 0)) if home and home.get('score') is not None else 0
        away_score = int(away.get('score', 0)) if away and away.get('score') is not None else 0
        # vencedor
        if home_score > away_score:
            winner = home_abbr
        elif away_score > home_score:
            winner = away_abbr
        else:
            winner = "Empate"
        return {
            'id': evt.get('id'),
            'name': evt.get('name', ''),
            'date': data_formatada,
            'timestamp': data_obj.isoformat() if data_obj else "",
            'status': status_pt,
            'home': home_abbr,
            'away': away_abbr,
            'home_score': home_score,
            'away_score': away_score,
            'winner': winner,
            'home_logo': get_logo_url(home_abbr),
            'away_logo': get_logo_url(away_abbr)
        }
    except Exception as e:
        return None

@st.cache_data(ttl=120)
def load_events_live():
    """
    Usa o endpoint /scoreboard para capturar jogos agendados, em andamento e finalizados recentes.
    """
    try:
        resp = requests.get(API_URL_SCOREBOARD, timeout=10)
        resp.raise_for_status()
        j = resp.json()
        events = j.get('events', [])
        parsed = []
        for e in events:
            p = parse_event_from_scoreboard(e)
            if p:
                parsed.append(p)
        parsed.sort(key=lambda x: x['timestamp'] or "")
        return parsed
    except Exception as e:
        st.error(f"Erro carregando eventos ao vivo: {e}")
        return []

@st.cache_data(ttl=3600)
def load_events_historical():
    """
    Carrega os eventos históricos da temporada (usando endpoint events?dates=2025).
    """
    try:
        resp = requests.get(API_URL_EVENTS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        events_raw = data.get('events', [])
        all_events = []
        for e in events_raw:
            # Para pegar detalhes completos, usar o link $ref
            comp_url = e.get('$ref')
            if not comp_url:
                # se não tiver $ref, talvez o próprio `e` já seja detalhado
                parsed = parse_event_from_scoreboard(e)
                if parsed:
                    all_events.append(parsed)
            else:
                try:
                    comp_resp = requests.get(comp_url, timeout=10)
                    comp_resp.raise_for_status()
                    full = comp_resp.json()
                    parsed = parse_event_from_scoreboard(full)
                    if parsed:
                        all_events.append(parsed)
                except Exception:
                    continue
        # ordenar por timestamp
        all_events.sort(key=lambda x: x['timestamp'] or "")
        return all_events
    except Exception as e:
        st.warning(f"Erro ao carregar eventos históricos: {e}")
        return []

# --- Combinação dos eventos live + históricos ---
live_events = load_events_live()
historical_events = load_events_historical()

# usar dicionário para evitar duplicatas por ID
events_by_id = {}
for e in historical_events:
    if e.get('id'):
        events_by_id[e['id']] = e
for e in live_events:
    if e.get('id'):
        events_by_id[e['id']] = e

events = list(events_by_id.values())

if not events:
    st.warning("Nenhum jogo disponível no momento.")
else:
    # definir o início da temporada a partir do evento mais antigo
    try:
        earliest_ts = min([e['timestamp'] for e in events if e.get('timestamp')])
        season_start = isoparse(earliest_ts).date()
    except Exception:
        season_start = datetime.now().date()

def week_of(dt_iso):
    """Calcula número da semana a partir do season_start."""
    try:
        dt = isoparse(dt_iso).date()
        delta = (dt - season_start).days
        wk = math.floor(delta / 7) + 1
        return max(1, wk)
    except:
        return 1

# organizar as listas por status
in_progress = [e for e in events if "Em Andamento" in e['status']]
scheduled = [e for e in events if "Agendado" in e['status']]
finalized = [e for e in events if e not in in_progress and e not in scheduled]

# agrupar por semana
weeks = {}
for e in events:
    wk = week_of(e.get('timestamp', ""))
    if wk >= 1:
        weeks.setdefault(wk, []).append(e)

def compute_standings(final_games):
    stats = {}
    for g in final_games:
        h = g['home']; a = g['away']
        hs = g['home_score']; as_ = g['away_score']
        for t in (h, a):
            stats.setdefault(t, {'team': t, 'W':0, 'L':0, 'T':0, 'PF':0, 'PA':0, 'games': []})
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
        wpct = (s['W'] + 0.5 * s['T']) / gp if gp > 0 else 0
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
            'PF': s['PF'], 'PA': s['PA'], 'Win%': round(wpct, 3), 'Streak': streak
        })
    rows.sort(key=lambda x: (x['Win%'], x['PF'] - x['PA']), reverse=True)
    return rows

standings = compute_standings(finalized)

def biggest_blowouts(final_games, top_n=5):
    arr = []
    for g in final_games:
        diff = abs(g['home_score'] - g['away_score'])
        arr.append((diff, g))
    arr.sort(reverse=True, key=lambda x: x[0])
    return [x[1] for x in arr[:top_n]]

blowouts = biggest_blowouts(finalized, top_n=5)

# payload para frontend
payload = {
    "sections": [
        {"title": "🔴 Jogos Ao Vivo", "games": in_progress},
        {"title": "⏳ Próximos Jogos", "games": scheduled},
        {"title": "✅ Resultados Recentes", "games": finalized}
    ],
    "weeks": weeks,
    "standings": standings,
    "blowouts": blowouts
}

payload_json = json.dumps(payload)

# HTML frontend (igual ao seu template anterior) — deixo como está,
# apenas substituindo a parte de PAYLOAD_JSON
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
        card.innerHTML = `
            <div class="meta">${g.date}</div>
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
const weeksRoot = document.createElement('div');
const wSec = document.createElement('div');
wSec.className = 'section';
const wh = document.createElement('h2');
wh.textContent = '📜 Histórico por Semana';
wSec.appendChild(wh);
Object.keys(payload.weeks).map(Number).sort((a,b)=>a-b).forEach(k=>{
    const arr = payload.weeks[k];
    if(!arr || arr.length===0) return;
    const block = document.createElement('div');
    block.className = 'week-block';
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.innerHTML = `Semana ${k} <span class="small">(${arr.length} jogos)</span>`;
    details.appendChild(summary);
    const inner = document.createElement('div');
    inner.className = 'small';
    arr.forEach(g=>{
        const homeClass = (g.winner === g.home && g.status === 'Finalizado') ? 'winner-text' : '';
        const awayClass = (g.winner === g.away && g.status === 'Finalizado') ? 'winner-text' : '';
        const line = document.createElement('div');
        line.innerHTML = `<span>${g.date}</span> — <span class="${homeClass}">${g.home}</span> ${g.home_score} - ${g.away_score} <span class="${awayClass}">${g.away}</span> <span class="small">· ${g.status}</span>`;
        inner.appendChild(line);
    });
    details.appendChild(inner);
    block.appendChild(details);
    wSec.appendChild(block);
});
root.appendChild(wSec);
const stSec = document.createElement('div');
stSec.className = 'section';
const sth2 = document.createElement('h2');
sth2.textContent = '🏆 Classificação (Finalizados)';
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
    stDiv.innerHTML = "<div class='small'>Sem dados suficientes.</div>";
}
stSec.appendChild(stDiv);
root.appendChild(stSec);
const boSec = document.createElement('div');
boSec.className = 'section';
const boh = document.createElement('h2');
boh.textContent = '💥 Maiores Vitórias';
boSec.appendChild(boh);
const boDiv = document.createElement('div');
boDiv.className = 'details';
payload.blowouts.forEach(g=>{
    const diff = Math.abs(g.home_score - g.away_score);
    const winner = g.home_score > g.away_score ? g.home : (g.away_score > g.home_score ? g.away : '');
    const winnerHomeScoreClass = (g.home_score > g.away_score) ? 'winner-text' : '';
    const winnerAwayScoreClass = (g.away_score > g.home_score) ? 'winner-text' : '';
    const p = document.createElement('p');
    p.innerHTML = `<span>${g.date}</span> — <span class="${winner===g.home?'winner-text':''}">${g.home}</span> <span class="${winnerHomeScoreClass}">${g.home_score}</span> - <span class="${winnerAwayScoreClass}">${g.away_score}</span> <span class="${winner===g.away?'winner-text':''}">${g.away}</span> <span class="small">· dif ${diff}</span>`;
    boDiv.appendChild(p);
});
boSec.appendChild(boDiv);
root.appendChild(boSec);
</script>
</body>
</html>
"""

html_code = html_template.replace("PAYLOAD_JSON", json.dumps(payload))

num = len(events)
rows = math.ceil(num / 3)
height = min(800 + rows * 120, 9000)

st.download_button("📥 Baixar histórico CSV", data=pd.DataFrame(events).to_csv(index=False).encode('utf-8'),
                   file_name="nfl_history.csv", mime="text/csv")

st.components.v1.html(html_code, height=height, scrolling=False)
