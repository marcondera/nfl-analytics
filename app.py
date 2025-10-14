# app.py
import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta
import json
import html

# Streamlit page config
st.set_page_config(page_title="NFL Results Dashboard — Redesigned", layout="wide", page_icon="🏈")

API_URL_EVENTS_2025 = "https://partners.api.espn.com/v2/sports/football/nfl/events?dates=2025"

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
    try:
        comp = event.get('competitions', [])[0]
        date_iso = comp.get('date')
        data_obj = isoparse(date_iso) if date_iso else None
        data_formatada = data_obj.strftime('%d/%m/%Y %H:%M') + " BRT" if data_obj else "N/A"

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

@st.cache_data(ttl=60)
def load_events(api_url):
    try:
        r = requests.get(api_url, timeout=8)
        r.raise_for_status()
        ev = r.json().get('events', [])
        parsed = [parse_event(e) for e in ev]
        parsed = [p for p in parsed if p is not None]
        # ensure chronological
        parsed.sort(key=lambda x: x['timestamp'] or "")
        return parsed
    except Exception:
        return []

# ---------- UI ----------
st.markdown("<h1 style='margin-bottom:4px'>🏈 NFL Results — Redesigned</h1>", unsafe_allow_html=True)

# Week header
hoje = datetime.now()
inicio_semana = hoje - timedelta(days=hoje.weekday())
fim_semana = inicio_semana + timedelta(days=6)
periodo_txt = f"{inicio_semana.strftime('%d/%m')} → {fim_semana.strftime('%d/%m')}"
st.markdown(f"<h3 style='color:#bfc7d6; margin-top:0'>📅 Resultados da Semana Atual ({periodo_txt})</h3>", unsafe_allow_html=True)

if st.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    st.experimental_rerun()

events = load_events(API_URL_EVENTS_2025)

if not events:
    st.warning("Nenhum dado disponível — verifique a API ou a conexão.")
    st.stop()

# Group by status for display order: in progress, scheduled, finalized
in_progress = [e for e in events if "Andamento" in e['status'] or "Andando" in e['status'] or "Em Andamento" in e['status']]
scheduled = [e for e in events if "Agendado" in e['status']]
finalized = [e for e in events if e not in in_progress and e not in scheduled]

# combine but keep consistent layout
display_order = [
    ("🔴 Jogos Ao Vivo", in_progress),
    ("⏳ Próximos Jogos", scheduled),
    ("✅ Resultados Recentes", finalized)
]

# Prepare JSON data for the HTML renderer
payload = {
    "sections": []
}
for title, lst in display_order:
    payload["sections"].append({
        "title": title,
        "games": lst
    })

# Also prepare CSV download
df_hist = pd.DataFrame(events)
csv_bytes = df_hist.to_csv(index=False).encode('utf-8')

st.download_button("📥 Baixar histórico (CSV)", data=csv_bytes, file_name="nfl_history.csv", mime="text/csv")

# Build HTML/JS frontend (responsive grid, polished styling)
html_content = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg:#0e1117;
    --card:#11151b;
    --muted:#9aa4b2;
    --accent:#4CAF50;
    --danger:#FF4B4B;
    --glass: rgba(255,255,255,0.03);
  }}
  html,body{{background:var(--bg); color:#fff; font-family:Inter,system-ui,Segoe UI,Roboto;}}
  .wrap{{padding:18px; box-sizing:border-box;}}
  .section-title{{font-size:20px; color:#e6eef8; margin:12px 0 10px; display:flex; align-items:center; gap:10px}}
  .grid{{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:40px 18px; align-items:start;}}
  .card{{
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    border-radius:12px; padding:16px; box-shadow: 0 6px 18px rgba(0,0,0,0.6);
    border: 1px solid rgba(255,255,255,0.03);
    display:flex; flex-direction:column; gap:10px;
  }}
  .meta{{display:flex; justify-content:space-between; align-items:center; color:var(--muted); font-size:13px;}}
  .teams{{display:flex; align-items:center; justify-content:center; gap:8px;}}
  .team{{display:flex; align-items:center; gap:8px; min-width:0;}}
  .logo{{width:56px; height:56px; object-fit:contain; display:block; margin:0;}}
  /* negative margin to bring logos very close to score */
  .logo.left{{margin-right:-10px}} 
  .logo.right{{margin-left:-10px}} 
  .score-wrap{{display:flex; align-items:center; justify-content:center; gap:6px; min-width:120px;}}
  .score{{font-size:3.6rem; font-weight:900; line-height:0.9; letter-spacing:-2px; color:#fff;}}
  .team-name{{font-weight:600; font-size:0.95rem; color:#dfe8f5; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:70px; text-align:center;}}
  .status{{text-align:center; color:var(--muted); font-size:0.9rem; margin-top:6px;}}
  .row-center{{display:flex; align-items:center; justify-content:center; gap:12px;}}
  /* small badge for winner */
  .winner-badge{{background:linear-gradient(90deg,var(--accent),#2fa14f); color:#04120a; font-weight:800;
                 padding:4px 8px; border-radius:999px; font-size:0.8rem;}}
  .loser-text{{color:var(--danger); font-weight:600;}}
  /* table */
  .hist-wrap{{margin-top:24px;}}
  table.hist{{width:100%; border-collapse:collapse; font-size:0.95rem;}}
  table.hist th, table.hist td{{padding:10px; text-align:center; border-bottom:1px solid rgba(255,255,255,0.03);}}
  table.hist th{{color:var(--muted); font-weight:600; font-size:0.85rem;}}
  .winner-cell{{color:var(--accent); font-weight:800;}}
  .loser-cell{{color:var(--danger); opacity:0.95; font-weight:700;}}
  /* responsive tweaks */
  @media (max-width:560px){ .score{{font-size:2.4rem}} .logo{{width:44px;height:44px}} .team-name{{max-width:60px}} }
</style>
</head>
<body>
<div class="wrap">
  <!-- sections will be injected -->
  <div id="sections"></div>

  <div class="hist-wrap">
    <h3 style="margin:8px 0 10px; color:#e6eef8">📜 Histórico Completo (Semana Atual: {html.escape(periodo_txt)})</h3>
    <div style="overflow:auto; border-radius:10px; padding:8px; background:var(--glass);">
      <table class="hist" id="hist-table">
        <thead>
          <tr><th>Data</th><th>Jogo</th><th>Casa</th><th>Pts</th><th>Visitante</th><th>Pts</th><th>Status</th></tr>
        </thead>
        <tbody id="hist-body"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
(function(){
  const payload = {html_payload};
  const secRoot = document.getElementById('sections');

  function makeCard(g){
    // create card element
    const c = document.createElement('div');
    c.className = 'card';
    // meta row: date and maybe winner badge
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerHTML = `<div style="font-size:13px;color:var(--muted)">${g.date}</div>
                      <div>${g.status.includes('Finalizado') ? '<span class="winner-badge">Resultado</span>' : ''}</div>`;
    c.appendChild(meta);

    // teams row (logos + score)
    const teams = document.createElement('div');
    teams.className = 'row-center';

    const tleft = document.createElement('div');
    tleft.className = 'team';
    tleft.innerHTML = `<img class="logo left" src="${g.home_logo}" alt="${g.home}"/><div class="team-name">${g.home}</div>`;

    const scorewrap = document.createElement('div');
    scorewrap.className = 'score-wrap';
    // highlight winner when finalized
    let leftClass = '';
    let rightClass = '';
    if(g.winner && g.winner !== 'Empate' && g.status.includes('Finalizado')){
      if(g.winner === g.home) leftClass = 'winner-cell'; else rightClass='winner-cell';
      if(g.winner === g.away) rightClass = 'winner-cell'; else leftClass = leftClass || '';
    }

    scorewrap.innerHTML = `<div class="score"><span class="${leftClass}">${g.home_score}</span> <span style="opacity:0.6; font-size:0.6em; font-weight:700; margin:0 4px">-</span> <span class="${rightClass}">${g.away_score}</span></div>`;

    const tright = document.createElement('div');
    tright.className = 'team';
    tright.innerHTML = `<div class="team-name">${g.away}</div><img class="logo right" src="${g.away_logo}" alt="${g.away}"/>`;

    teams.appendChild(tleft);
    teams.appendChild(scorewrap);
    teams.appendChild(tright);

    c.appendChild(teams);

    // status
    const s = document.createElement('div');
    s.className = 'status';
    s.textContent = g.status;
    c.appendChild(s);

    return c;
  }

  // render sections
  payload.sections.forEach(section=>{
    if(!section.games || section.games.length===0) return;
    const title = document.createElement('div');
    title.className = 'section-title';
    title.innerHTML = `<strong>${section.title}</strong>`;
    secRoot.appendChild(title);

    const grid = document.createElement('div');
    grid.className = 'grid';
    section.games.forEach(g => {
      grid.appendChild(makeCard(g));
    });
    secRoot.appendChild(grid);
  });

  // history table
  const histBody = document.getElementById('hist-body');
  // sort by timestamp already sorted in backend; just render
  payload.sections.flatMap(s=>s.games).forEach(g=>{
    const tr = document.createElement('tr');
    const homeClass = (g.winner === g.home && g.status.includes('Finalizado')) ? 'winner-cell' : (g.winner === g.away && g.status.includes('Finalizado')) ? 'loser-cell' : '';
    const awayClass = (g.winner === g.away && g.status.includes('Finalizado')) ? 'winner-cell' : (g.winner === g.home && g.status.includes('Finalizado')) ? 'loser-cell' : '';
    tr.innerHTML = `<td>${g.date}</td>
                    <td>${g.name}</td>
                    <td class="${homeClass}">${g.home}</td>
                    <td class="${homeClass}">${g.home_score}</td>
                    <td class="${awayClass}">${g.away}</td>
                    <td class="${awayClass}">${g.away_score}</td>
                    <td>${g.status}</td>`;
    histBody.appendChild(tr);
  });

})(); 
</script>
</body>
</html>
""".replace("{html_payload}", html.escape(json.dumps(payload)))

# Render the HTML in Streamlit; allow height large enough for many cards
st.components.v1.html(html_content, height=900, scrolling=True)
