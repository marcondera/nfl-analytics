import streamlit as st
import pandas as pd
import requests
from dateutil.parser import isoparse
from datetime import datetime, timedelta
import json

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="🏈 NFL Results Dashboard", layout="wide", page_icon="🏈")

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
    try:
        r = requests.get(API_URL_EVENTS_2025, timeout=10)
        r.raise_for_status()
        events = r.json().get('events', [])
        data = [parse_event(e) for e in events if e]
        data = [d for d in data if d]
        data.sort(key=lambda x: x['timestamp'])
        return data
    except Exception:
        return []

# --- INTERFACE ---
st.markdown("<h1 style='margin-bottom:4px'>🏈 NFL Results Dashboard</h1>", unsafe_allow_html=True)

if st.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

events = load_events()
if not events:
    st.warning("Nenhum dado disponível no momento.")
    st.stop()

# Separar por status
in_progress = [e for e in events if "Andamento" in e['status']]
scheduled = [e for e in events if "Agendado" in e['status']]
finalized = [e for e in events if e not in in_progress and e not in scheduled]

payload = {"sections": [
    {"title": "🔴 Jogos Ao Vivo", "games": in_progress},
    {"title": "⏳ Próximos Jogos", "games": scheduled},
    {"title": "✅ Resultados Recentes", "games": finalized},
    {"title": "📅 Histórico Completo da Temporada", "games": events}
]}

html_template = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0e1117;
  --card: #1b1f28;
  --muted: #9aa4b2;
  --accent: #4CAF50;
  --danger: #FF4B4B;
}
body {
  background: var(--bg);
  color: #fff;
  font-family: Inter, sans-serif;
  margin: 0;
  padding: 0;
  overflow-x: hidden;
}
.container {
  padding: 24px;
  max-width: 1300px;
  margin: auto;
}
.section {
  margin-bottom: 60px;
}
.section h2 {
  font-size: 1.6rem;
  margin-bottom: 20px;
  color: #e6eef8;
  border-left: 5px solid var(--accent);
  padding-left: 10px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 26px;
}
.card {
  background: var(--card);
  border-radius: 14px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.6);
}
.meta {
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 8px;
}
.teams {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.team {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 70px;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
  padding: 4px;
  box-sizing: border-box;
}
.logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.score {
  font-size: 3rem;
  font-weight: 900;
  margin: 0 6px;
  color: #fff;
}
.status {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 10px;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
  color: #e6eef8;
  font-size: 0.95rem;
}
th, td {
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding: 8px 6px;
  text-align: center;
}
th {
  color: var(--muted);
}
.winner {
  color: var(--accent);
  font-weight: 800;
}
.loser {
  color: var(--danger);
  font-weight: 700;
}
@media (max-width:600px) {
  .score { font-size: 2.2rem; }
  .logo { width: 48px; height: 48px; }
}
</style>
</head>
<body>
<div class="container" id="root"></div>
<script>
const payload = PAYLOAD_JSON;
const root = document.getElementById("root");

payload.sections.forEach(section => {
  if (!section.games || section.games.length === 0) return;
  const div = document.createElement("div");
  div.className = "section";
  const h2 = document.createElement("h2");
  h2.textContent = section.title;
  div.appendChild(h2);
  const grid = document.createElement("div");
  grid.className = "grid";

  section.games.forEach(g => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="meta">${g.date}</div>
      <div class="teams">
        <div class="team">
          <div class="logo"><img src="${g.home_logo}" alt="${g.home}"></div>
          <div>${g.home}</div>
        </div>
        <div class="score">${g.home_score} - ${g.away_score}</div>
        <div class="team">
          <div class="logo"><img src="${g.away_logo}" alt="${g.away}"></div>
          <div>${g.away}</div>
        </div>
      </div>
      <div class="status">${g.status}</div>
    `;
    grid.appendChild(card);
  });
  div.appendChild(grid);

  if (section.title.includes("Histórico")) {
    const table = document.createElement("table");
    table.innerHTML = `
      <thead>
        <tr><th>Data</th><th>Casa</th><th>Pts</th><th>Visitante</th><th>Pts</th><th>Status</th></tr>
      </thead>
      <tbody>
        ${section.games.map(g => {
          let homeClass = "", awayClass = "";
          if (g.status.startsWith("Finalizado")) {
            if (g.winner === g.home) homeClass = "winner", awayClass = "loser";
            else if (g.winner === g.away) awayClass = "winner", homeClass = "loser";
          }
          return `<tr>
            <td>${g.date}</td>
            <td class="${homeClass}">${g.home}</td>
            <td class="${homeClass}">${g.home_score}</td>
            <td class="${awayClass}">${g.away}</td>
            <td class="${awayClass}">${g.away_score}</td>
            <td>${g.status}</td>
          </tr>`;
        }).join("")}
      </tbody>`;
    div.appendChild(table);
  }
  root.appendChild(div);
});
</script>
</body>
</html>
"""

html_code = html_template.replace("PAYLOAD_JSON", json.dumps(payload))
st.components.v1.html(html_code, height=2400, scrolling=False)
