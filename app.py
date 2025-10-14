# app.py
import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta
import json, math

# --- CONFIG ---
st.set_page_config(page_title="🏈 NFL Results Dashboard", layout="wide", page_icon="🏈")

API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

# map de logos (mantive seu mapeamento)
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

def parse_event(event):
    """
    Parse event JSON from ESPN partners API into flattened dict used by the UI.
    Removes 'BRT' suffix and keeps a timestamp ISO string for sorting.
    """
    try:
        comp = event.get('competitions', [])[0]
        date_iso = comp.get('date')
        data_obj = isoparse(date_iso) if date_iso else None
        # remove timezone suffix; show local naive formatted datetime
        data_formatada = data_obj.strftime('%d/%m/%Y %H:%M') if data_obj else "N/A"

        status = comp.get('status', {})
        stype = status.get('type', {}) or {}
        stype_text = str(stype).lower()

        if 'final' in stype_text:
            status_pt = 'Finalizado (Prorrogação)' if 'ot' in stype_text else 'Finalizado'
        elif stype.get('state') == 'in':
            clock = status.get('displayClock', '0:00')
            period = status.get('period', 1)
            status_pt = f"Em Andamento – {clock} restantes no {get_period_name(period)}"
        elif stype.get('state') == 'pre':
            status_pt = 'Agendado'
        else:
            status_pt = stype.get('description', 'Status Desconhecido')

        competitors = comp.get('competitors', [])
        home = competitors[0] if len(competitors) > 0 else {}
        away = competitors[1] if len(competitors) > 1 else {}

        home_abbr = home.get('team', {}).get('abbreviation', 'CASA')
        away_abbr = away.get('team', {}).get('abbreviation', 'FORA')

        # ensure integer scores
        home_score = int(home.get('score', {}).get('value', 0)) if home.get('score') else 0
        away_score = int(away.get('score', {}).get('value', 0)) if away.get('score') else 0

        winner = home_abbr if home_score > away_score else away_abbr if away_score > home_score else "Empate"

        return {
            'id': event.get('id', ''),
            'name': event.get('name', ''),
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
    except Exception:
        return None

@st.cache_data(ttl=120)
def load_events():
    """
    Load events from ESPN API and return a list of parsed event dicts sorted by timestamp.
    """
    try:
        r = requests.get(API_URL_EVENTS_2025, timeout=12)
        r.raise_for_status()
        ev = r.json().get('events', [])
        parsed = [parse_event(e) for e in ev]
        parsed = [p for p in parsed if p is not None]
        parsed.sort(key=lambda x: x['timestamp'] or "")
        return parsed
    except Exception:
        return []

# ---------------- UI (Streamlit wrapper around a custom HTML frontend) ----------------
st.markdown("<h1 style='margin-bottom:4px'>🏈 NFL Results Dashboard — Enhanced</h1>", unsafe_allow_html=True)

if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

events = load_events()
if not events:
    st.warning("Nenhum dado disponível — verifique a API.")
    st.stop()

# derive buckets and statistics
in_progress = [e for e in events if "Andamento" in e['status']]
scheduled = [e for e in events if "Agendado" in e['status']]
finalized = [e for e in events if e not in in_progress and e not in scheduled]

# Prepare weekly grouping for history: compute week number relative to season start
# Use earliest event date as season start if possible, else fallback to Sep 4, 2025
try:
    first_ts = min([e['timestamp'] for e in events if e['timestamp']])
    season_start = isoparse(first_ts).date()
except Exception:
    season_start = datetime(2025,9,4).date()

def week_of(dt_iso):
    try:
        dt = isoparse(dt_iso).date()
        # week number counting from season_start as week 1
        delta_days = (dt - season_start).days
        week_num = (delta_days // 7) + 1
        return max(1, week_num)
    except Exception:
        return 0

# group events by week number
weeks = {}
for e in events:
    wk = week_of(e['timestamp']) if e['timestamp'] else 0
    weeks.setdefault(wk, []).append(e)

# Build standings from finalized games
def compute_standings(finalized_games):
    # stats per team
    stats = {}
    for g in finalized_games:
        h = g['home']; a = g['away']; hs = g['home_score']; ascore = g['away_score']
        for t in (h,a):
            if t not in stats:
                stats[t] = {'team': t, 'W':0,'L':0,'T':0,'PF':0,'PA':0,'PD':0,'games':[]}
        stats[h]['PF'] += hs
        stats[h]['PA'] += ascore
        stats[a]['PF'] += ascore
        stats[a]['PA'] += hs
        stats[h]['PD'] = stats[h]['PF'] - stats[h]['PA']
        stats[a]['PD'] = stats[a]['PF'] - stats[a]['PA']
        # result
        if hs > ascore:
            stats[h]['W'] += 1
            stats[a]['L'] += 1
            stats[h]['games'].append('W'); stats[a]['games'].append('L')
        elif ascore > hs:
            stats[a]['W'] += 1
            stats[h]['L'] += 1
            stats[a]['games'].append('W'); stats[h]['games'].append('L')
        else:
            stats[h]['T'] += 1; stats[a]['T'] += 1
            stats[h]['games'].append('T'); stats[a]['games'].append('T')
    # convert to list with pct and streak
    rows = []
    for t, s in stats.items():
        gp = s['W'] + s['L'] + s['T']
        wpct = (s['W'] + 0.5*s['T']) / gp if gp>0 else 0.0
        # streak: look at last games list reversed
        streak = ''
        if s['games']:
            run = s['games'][::-1]
            cur = run[0]
            cnt = 1
            for r in run[1:]:
                if r==cur: cnt += 1
                else: break
            streak = f"{cur}{cnt}"
        rows.append({
            'Team': t, 'W': s['W'], 'L': s['L'], 'T': s['T'],
            'PF': s['PF'], 'PA': s['PA'], 'PD': s['PD'],
            'Win%': round(wpct,3), 'GP': gp, 'Streak': streak
        })
    # sort by Win%, then PD, then PF
    rows.sort(key=lambda r: (r['Win%'], r['PD'], r['PF']), reverse=True)
    return rows

standings = compute_standings(finalized)

# Additional fan-focused stats: biggest blowouts, longest win streaks
def biggest_blowouts(finalized_games, top_n=5):
    arr = []
    for g in finalized_games:
        diff = abs(g['home_score'] - g['away_score'])
        arr.append((diff,g))
    arr.sort(reverse=True, key=lambda x: x[0])
    return [x[1] for x in arr[:top_n]]

blowouts = biggest_blowouts(finalized, top_n=6)

# Prepare payload for the HTML renderer
payload = {
    "summary": {
        "total_games": len(events),
        "in_progress": len(in_progress),
        "scheduled": len(scheduled),
        "finalized": len(finalized)
    },
    "sections": [
        {"title":"🔴 Jogos Ao Vivo", "games": in_progress},
        {"title":"⏳ Próximos Jogos", "games": scheduled},
        {"title":"✅ Resultados Recentes", "games": finalized}
    ],
    "weeks": weeks,
    "standings": standings,
    "blowouts": blowouts
}

# Convert payload to JSON text to embed
payload_json = json.dumps(payload)

# Build improved HTML UI
html_template = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0e1117; --card:#14171b; --muted:#98a3b0; --accent:#4CAF50; --danger:#FF4B4B;
}
html,body{height:100%; margin:0; padding:0; background:var(--bg); color:#fff; font-family:Inter,system-ui,Arial;}
.container{max-width:1200px; margin:16px auto; padding:12px;}
.header{display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px;}
.title{font-size:1.25rem; font-weight:800;}
.summary{display:flex; gap:12px; flex-wrap:wrap; align-items:center;}
.summary .card{background:linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding:10px 14px; border-radius:10px; color:var(--muted);}
.layout{display:grid; grid-template-columns: 2fr 1fr; gap:18px;}
@media(max-width:980px){ .layout{grid-template-columns:1fr} }
.section{background:transparent; padding:6px 0;}
.section h2{font-size:1.05rem; margin:6px 0 12px; color:#e6eef8; border-left:4px solid var(--accent); padding-left:8px;}
.grid{display:grid; grid-template-columns:repeat(auto-fill, minmax(250px,1fr)); gap:18px;}
.card{background:var(--card); border-radius:12px; padding:12px; box-shadow:0 6px 18px rgba(0,0,0,0.5); display:flex; flex-direction:column; align-items:center; transition: transform .18s ease;}
.card:hover{transform:translateY(-4px)}
.meta{font-size:0.82rem; color:var(--muted); margin-bottom:8px;}
.teams{display:flex; align-items:center; justify-content:center; gap:8px; width:100%;}
.team{display:flex; flex-direction:column; align-items:center; gap:6px; min-width:70px;}
.logo{width:56px; height:56px; border-radius:10px; background:#fff; overflow:hidden; display:flex; align-items:center; justify-content:center;}
.logo img{max-width:100%; max-height:100%; object-fit:contain; display:block;}
.score{font-size:2.6rem; font-weight:900; white-space:nowrap; margin:0 8px; line-height:1;}
.team-name{font-weight:700; font-size:0.95rem;}
.status{color:var(--muted); font-size:0.86rem; margin-top:8px; text-align:center;}
.right-column{display:flex; flex-direction:column; gap:12px;}
.table {width:100%; border-collapse:collapse; margin-top:8px; font-size:0.95rem;}
.table th, .table td {padding:8px 6px; border-bottom:1px solid rgba(255,255,255,0.06); text-align:center;}
.table th {color:var(--muted); font-weight:700;}
.winner-text{color:var(--accent); font-weight:800;}
.loser-text{color:var(--danger); font-weight:700;}
.details { background:var(--card); border-radius:10px; padding:10px; margin-top:8px; }
.week-block { margin-bottom:8px; }
.small { font-size:0.85rem; color:var(--muted); }
.badge { display:inline-block; padding:4px 8px; border-radius:999px; background:rgba(255,255,255,0.02); color:var(--muted); font-weight:700; font-size:0.82rem;}
.fade { transition:opacity .2s ease; }
@media (max-width:600px){ .score{font-size:2.0rem} .logo{width:48px;height:48px} .grid{gap:12px} }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <div class="title">🏈 NFL Results — Dashboard completo</div>
      <div class="small">Dados carregados da API — histórico, classificações e insights</div>
    </div>
    <div class="summary" id="summary"></div>
  </div>

  <div class="layout">
    <div>
      <!-- main sections -->
      <div id="main-sections"></div>

      <!-- weekly history as collapsible blocks -->
      <div class="section">
        <h2>📜 Histórico por semana</h2>
        <div id="weeks"></div>
      </div>
    </div>

    <div class="right-column">
      <div class="section">
        <h2>🏆 Classificação (apenas jogos finalizados)</h2>
        <div id="standings" class="details"></div>
      </div>

      <div class="section">
        <h2>💥 Maiores Vitórias (Blowouts)</h2>
        <div id="blowouts" class="details"></div>
      </div>

      <div class="section">
        <h2>🔍 Insights Rápidos</h2>
        <div id="insights" class="details"></div>
      </div>
    </div>
  </div>
</div>

<script>
const payload = PAYLOAD_JSON;

// summary
const sumRoot = document.getElementById('summary');
sumRoot.innerHTML = `
  <div class="badge">Total jogos: ${payload.summary.total_games}</div>
  <div class="badge">Ao vivo: ${payload.summary.in_progress}</div>
  <div class="badge">Agendados: ${payload.summary.scheduled}</div>
  <div class="badge">Finalizados: ${payload.summary.finalized}</div>
`;

// render sections (cards)
const main = document.getElementById('main-sections');
payload.sections.forEach(sec=>{
  if(!sec.games || sec.games.length===0) return;
  const sdiv = document.createElement('div');
  sdiv.className = 'section';
  const h = document.createElement('h2'); h.textContent = sec.title;
  sdiv.appendChild(h);
  const grid = document.createElement('div'); grid.className='grid';
  sec.games.forEach(g=>{
    const card = document.createElement('div'); card.className='card';
    // winner highlight only in text
    const homeClass = (g.winner === g.home && g.status.startsWith('Finalizado')) ? 'winner-text' : '';
    const awayClass = (g.winner === g.away && g.status.startsWith('Finalizado')) ? 'winner-text' : '';
    card.innerHTML = `
      <div class="meta">${g.date}</div>
      <div class="teams">
        <div class="team">
          <div class="logo"><img src="${g.home_logo}" alt="${g.home}"></div>
          <div class="team-name ${homeClass}">${g.home}</div>
        </div>
        <div class="score">${g.home_score} - ${g.away_score}</div>
        <div class="team">
          <div class="logo"><img src="${g.away_logo}" alt="${g.away}"></div>
          <div class="team-name ${awayClass}">${g.away}</div>
        </div>
      </div>
      <div class="status">${g.status}</div>
    `;
    grid.appendChild(card);
  });
  sdiv.appendChild(grid);
  main.appendChild(sdiv);
});

// weeks history using details summary (collapsible)
const weeksRoot = document.getElementById('weeks');
const weekKeys = Object.keys(payload.weeks).map(k=>parseInt(k,10)).sort((a,b)=>a-b);
weekKeys.forEach(k=>{
  const arr = payload.weeks[k];
  if(!arr || arr.length===0) return;
  const block = document.createElement('div'); block.className='week-block';
  const details = document.createElement('details');
  const summary = document.createElement('summary');
  summary.innerHTML = `<strong>Semana ${k}</strong> <span class="small">(${arr.length} jogos)</span>`;
  details.appendChild(summary);
  const inner = document.createElement('div'); inner.style.marginTop='8px';
  // simple list for week
  arr.forEach(g=>{
    const p = document.createElement('div'); p.className='small fade';
    const homeClass = (g.winner === g.home && g.status.startsWith('Finalizado')) ? 'winner-text' : '';
    const awayClass = (g.winner === g.away && g.status.startsWith('Finalizado')) ? 'winner-text' : '';
    p.innerHTML = `<span style="display:inline-block;width:150px">${g.date}</span>
                   <span class="${homeClass}">${g.home}</span>
                   <span style="margin:0 6px"> ${g.home_score} - ${g.away_score}</span>
                   <span class="${awayClass}">${g.away}</span>
                   <span style="color:var(--muted); margin-left:8px"> · ${g.status}</span>`;
    inner.appendChild(p);
  });
  details.appendChild(inner);
  block.appendChild(details);
  weeksRoot.appendChild(block);
});

// standings
const stRoot = document.getElementById('standings');
if(!payload.standings || payload.standings.length===0){
  stRoot.innerHTML = "<div class='small'>Sem jogos finalizados suficientes para gerar classificação.</div>";
} else {
  const t = document.createElement('table'); t.className='table';
  t.innerHTML = `<thead><tr><th>Pos</th><th>Time</th><th>W</th><th>L</th><th>T</th><th>PF</th><th>PA</th><th>PD</th><th>Win%</th><th>Streak</th></tr></thead>`;
  const tb = document.createElement('tbody');
  payload.standings.forEach((r,i)=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i+1}</td><td>${r.Team}</td><td>${r.W}</td><td>${r.L}</td><td>${r.T}</td>
                    <td>${r.PF}</td><td>${r.PA}</td><td>${r.PD}</td><td>${(r['Win%']).toFixed(3)}</td><td>${r.Streak||''}</td>`;
    tb.appendChild(tr);
  });
  t.appendChild(tb); stRoot.appendChild(t);
}

// blowouts
const blowRoot = document.getElementById('blowouts');
if(!payload.blowouts || payload.blowouts.length===0) blowRoot.innerHTML = "<div class='small'>Sem dados.</div>";
else {
  const ul = document.createElement('div'); ul.className='small';
  payload.blowouts.forEach(g=>{
    const diff = Math.abs(g.home_score - g.away_score);
    const winner = g.home_score>g.away_score ? g.home : (g.away_score>g.home_score ? g.away : 'Empate');
    ul.innerHTML += `<div style="margin-bottom:8px"> <strong class="small">${g.name}</strong><br>
                     <span>${g.date} — <span class="${winner===g.home? 'winner-text':''}">${g.home}</span> ${g.home_score} x ${g.away_score} <span class="${winner===g.away? 'winner-text':''}">${g.away}</span>
                     <span style="color:var(--muted)"> · diff ${diff}</span></span></div>`;
  });
  blowRoot.appendChild(ul);
}

// quick insights
const ins = document.getElementById('insights');
let longestWin = null;
let longestLen = 0;
const streaks = {};
payload.sections.forEach(sec=>sec.games.forEach(g=>{
  if(g.status.startsWith('Finalizado')){
    const w = g.winner;
    streaks[w] = streaks[w] ? streaks[w]+1 : 1;
    if(streaks[w] > longestLen){ longestLen = streaks[w]; longestWin = w; }
  }
}));
ins.innerHTML = `<div class="small">Maior sequência (apenas com dados): <strong>${longestWin or 'N/A'}</strong> — ${longestLen}</div>
                 <div class="small" style="margin-top:6px">Total partidas carregadas: <strong>${payload.summary.total_games}</strong></div>
                 <div class="small">Última atualização do painel: <strong>${new Date().toLocaleString()}</strong></div>`;

</script>
</body>
</html>
"""

# insert JSON payload safely (not escaped)
html_code = html_template.replace("PAYLOAD_JSON", json.dumps(payload))

# Set component height dynamically based on number of events (to avoid cutting off)
approx_card_height = 280  # px per row approx
num_cards = max(1, len(events))
# estimate rows (3 columns approx) -> rows = ceil(num_cards/3)
rows = math.ceil(num_cards / 3)
height = min(900 + rows * 120, 9000)  # cap to avoid browser weirdness

st.download_button("📥 Baixar histórico completo (CSV)", data=pd.DataFrame(events).to_csv(index=False).encode('utf-8'),
                   file_name="nfl_history.csv", mime="text/csv")

# render
st.components.v1.html(html_code, height=height, scrolling=False)
