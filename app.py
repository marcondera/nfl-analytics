import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta
import json

# --- CONFIGURAÇÃO ---
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
        r = requests.get(api_url, timeout=10)
        r.raise_for_status()
        ev = r.json().get('events', [])
        parsed = [parse_event(e) for e in ev]
        parsed = [p for p in parsed if p is not None]
        parsed.sort(key=lambda x: x['timestamp'] or "")
        return parsed
    except Exception:
        return []

# ---------- UI ----------
st.markdown("<h1 style='margin-bottom:4px'>🏈 NFL Results — Redesigned</h1>", unsafe_allow_html=True)

# Semana atual
hoje = datetime.now()
inicio_semana = hoje - timedelta(days=hoje.weekday())
fim_semana = inicio_semana + timedelta(days=6)
periodo_txt = f"{inicio_semana.strftime('%d/%m')} → {fim_semana.strftime('%d/%m')}"
st.markdown(f"<h3 style='color:#bfc7d6; margin-top:0'>📅 Resultados da Semana Atual ({periodo_txt})</h3>", unsafe_allow_html=True)

# Botão de recarregar
if st.button("🔄 Recarregar dados"):
    st.cache_data.clear()
    st.rerun()  # <- substitui o antigo experimental_rerun

events = load_events(API_URL_EVENTS_2025)
if not events:
    st.warning("Nenhum dado disponível — verifique a API.")
    st.stop()

# Agrupar por status
in_progress = [e for e in events if "Andamento" in e['status']]
scheduled = [e for e in events if "Agendado" in e['status']]
finalized = [e for e in events if e not in in_progress and e not in scheduled]

payload = {"sections": [
    {"title": "🔴 Jogos Ao Vivo", "games": in_progress},
    {"title": "⏳ Próximos Jogos", "games": scheduled},
    {"title": "✅ Resultados Recentes", "games": finalized}
]}

# Histórico CSV download
df_hist = pd.DataFrame(events)
st.download_button(
    "📥 Baixar histórico (CSV)",
    data=df_hist.to_csv(index=False).encode("utf-8"),
    file_name="nfl_history.csv",
    mime="text/csv"
)

# HTML Template seguro
html_template = """
<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>
:root{--bg:#0e1117;--card:#11151b;--muted:#9aa4b2;--accent:#4CAF50;--danger:#FF4B4B;}
body{background:var(--bg);color:#fff;font-family:Inter,system-ui,sans-serif;margin:0;padding:0;}
.wrap{padding:20px;}
.section-title{font-size:20px;color:#e6eef8;margin:12px 0 10px;}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:36px 16px;}
.card{background:rgba(255,255,255,0.03);border-radius:12px;padding:16px;box-shadow:0 4px 12px rgba(0,0,0,0.4);}
.meta{font-size:13px;color:var(--muted);margin-bottom:6px;display:flex;justify-content:space-between;}
.row-center{display:flex;align-items:center;justify-content:center;gap:10px;}
.team{display:flex;align-items:center;gap:8px;}
.logo{width:56px;height:56px;object-fit:contain;}
.score{font-size:3.4rem;font-weight:900;line-height:0.9;margin:0;}
.team-name{font-weight:600;font-size:1rem;color:#dfe8f5;max-width:70px;overflow:hidden;text-overflow:ellipsis;text-align:center;}
.status{text-align:center;color:var(--muted);font-size:0.9rem;margin-top:8px;}
.winner-cell{color:var(--accent);font-weight:800;}
.loser-cell{color:var(--danger);}
@media(max-width:560px){.score{font-size:2.4rem}.logo{width:44px;height:44px}.team-name{max-width:60px}}
</style>
</head>
<body>
<div class="wrap" id="root"></div>
<script>
const payload = PAYLOAD_JSON;
const root = document.getElementById('root');

payload.sections.forEach(section=>{
  if(!section.games || section.games.length===0) return;
  const title=document.createElement('div');
  title.className='section-title';
  title.textContent=section.title;
  root.appendChild(title);
  const grid=document.createElement('div');
  grid.className='grid';
  section.games.forEach(g=>{
    const card=document.createElement('div');
    card.className='card';
    card.innerHTML=`
      <div class="meta">${g.date} <span>${g.status.includes('Finalizado')?'🏁':''}</span></div>
      <div class="row-center">
        <div class="team"><img class="logo" src="${g.home_logo}"><div class="team-name">${g.home}</div></div>
        <div class="score"><span>${g.home_score}</span><span style="opacity:0.6">-</span><span>${g.away_score}</span></div>
        <div class="team"><div class="team-name">${g.away}</div><img class="logo" src="${g.away_logo}"></div>
      </div>
      <div class="status">${g.status}</div>`;
    grid.appendChild(card);
  });
  root.appendChild(grid);
});
</script>
</body>
</html>
"""

# Injetar JSON sem escapar (string normal)
html_code = html_template.replace("PAYLOAD_JSON", json.dumps(payload))
st.components.v1.html(html_code, height=None, scrolling=True)
