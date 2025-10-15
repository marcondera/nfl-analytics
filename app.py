import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime
from io import StringIO

# ========================
# CONFIGURAÇÃO BÁSICA
# ========================
CURRENT_PFR_YEAR = 2025
st.set_page_config(
    page_title=f"🏈 NFL Analytics {CURRENT_PFR_YEAR}",
    layout="wide",
    page_icon="🏈"
)

NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

LOGO_MAP = {
    "SF": "sf", "BUF": "buf", "ATL": "atl", "BAL": "bal", "CAR": "car", "CIN": "cin",
    "CHI": "chi", "CLE": "cle", "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
    "HOU": "hou", "IND": "ind", "JAX": "jac", "KC": "kc", "LAC": "lac", "LAR": "lar",
    "LV": "lv", "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no", "NYG": "nyg",
    "NYJ": "nyj", "PHI": "phi", "PIT": "pit", "SEA": "sea", "TB": "tb", "TEN": "ten",
    "ARI": "ari", "WAS": "wsh", "WSH": "wsh"
}

TEAM_CONFERENCE_DIVISION_MAP = {
    'BUF': {'conf': 'AFC', 'div': 'East'}, 'MIA': {'conf': 'AFC', 'div': 'East'},
    'NE': {'conf': 'AFC', 'div': 'East'}, 'NYJ': {'conf': 'AFC', 'div': 'East'},
    'BAL': {'conf': 'AFC', 'div': 'North'}, 'CIN': {'conf': 'AFC', 'div': 'North'},
    'CLE': {'conf': 'AFC', 'div': 'North'}, 'PIT': {'conf': 'AFC', 'div': 'North'},
    'HOU': {'conf': 'AFC', 'div': 'South'}, 'IND': {'conf': 'AFC', 'div': 'South'},
    'JAX': {'conf': 'AFC', 'div': 'South'}, 'TEN': {'conf': 'AFC', 'div': 'South'},
    'DEN': {'conf': 'AFC', 'div': 'West'}, 'KC': {'conf': 'AFC', 'div': 'West'},
    'LV': {'conf': 'AFC', 'div': 'West'}, 'LAC': {'conf': 'AFC', 'div': 'West'},
    'DAL': {'conf': 'NFC', 'div': 'East'}, 'NYG': {'conf': 'NFC', 'div': 'East'},
    'PHI': {'conf': 'NFC', 'div': 'East'}, 'WSH': {'conf': 'NFC', 'div': 'East'},
    'CHI': {'conf': 'NFC', 'div': 'North'}, 'DET': {'conf': 'NFC', 'div': 'North'},
    'GB': {'conf': 'NFC', 'div': 'North'}, 'MIN': {'conf': 'NFC', 'div': 'North'},
    'ATL': {'conf': 'NFC', 'div': 'South'}, 'CAR': {'conf': 'NFC', 'div': 'South'},
    'NO': {'conf': 'NFC', 'div': 'South'}, 'TB': {'conf': 'NFC', 'div': 'South'},
    'ARI': {'conf': 'NFC', 'div': 'West'}, 'LAR': {'conf': 'NFC', 'div': 'West'},
    'SF': {'conf': 'NFC', 'div': 'West'}, 'SEA': {'conf': 'NFC', 'div': 'West'}
}

# ========================
# CSS
# ========================
def inject_css():
    st.markdown("""
    <style>
    body {font-family: 'Inter', sans-serif;}
    .big-title {font-size:2.2em;font-weight:800;color:#222;margin-bottom:10px;}
    .section-title {font-size:1.5em;font-weight:700;margin-top:25px;margin-bottom:8px;}
    .subtext {color:#6c757d;font-size:0.9em;}
    .metric-card {background:#fff;border-radius:12px;padding:15px;box-shadow:0 2px 6px rgba(0,0,0,0.05);text-align:center;}
    .data-card {background:#fafafa;border-radius:10px;padding:12px;margin-bottom:10px;}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ========================
# FUNÇÕES
# ========================
@st.cache_data(ttl=3600)
def load_nflverse_data(year):
    df = pd.read_csv(NFLVERSE_GAMES_URL)
    df = df[(df["season"] == year) & (df["game_type"] == "REG")].copy()
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce").fillna(0)
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce").fillna(0)
    df = df[(df["home_score"] > 0) | (df["away_score"] > 0)].copy()

    def std(abbr):
        if abbr == "WAS": return "WSH"
        return abbr

    results = []
    for _, r in df.iterrows():
        winner, loser = (r["home_team"], r["away_team"]) if r["home_score"] >= r["away_score"] else (r["away_team"], r["home_team"])
        winner_pts = int(max(r["home_score"], r["away_score"]))
        loser_pts = int(min(r["home_score"], r["away_score"]))
        date = datetime.strptime(str(r["gameday"]), "%Y-%m-%d").strftime("%d %b %Y")
        results.append({
            "Week": int(r["week"]),
            "Date": date,
            "Winner": std(winner),
            "Loser": std(loser),
            "WinnerPts": winner_pts,
            "LoserPts": loser_pts,
        })
    return pd.DataFrame(results)

@st.cache_data(ttl=600)
def get_current_week():
    try:
        data = requests.get(API_URL_SCOREBOARD).json()
        txt = data.get("week", {}).get("text", "")
        num = "".join(ch for ch in txt if ch.isdigit())
        return int(num) if num else None
    except Exception:
        return None

def calculate_standings(df):
    table = {t: {"W":0,"L":0,"T":0} for t in TEAM_CONFERENCE_DIVISION_MAP}
    for _, r in df.iterrows():
        w, l = r["Winner"], r["Loser"]
        table[w]["W"] += 1
        table[l]["L"] += 1
    standings = pd.DataFrame.from_dict(table, orient="index").reset_index().rename(columns={"index":"Team"})
    standings["Conf"] = standings["Team"].apply(lambda t: TEAM_CONFERENCE_DIVISION_MAP[t]["conf"])
    standings["Div"] = standings["Team"].apply(lambda t: TEAM_CONFERENCE_DIVISION_MAP[t]["div"])
    standings["PCT"] = (standings["W"] / (standings["W"]+standings["L"]).replace(0,1)).round(3)
    return standings

# ========================
# INTERFACE
# ========================
st.markdown(f"<div class='big-title'>🏈 NFL Analytics {CURRENT_PFR_YEAR}</div>", unsafe_allow_html=True)
st.caption("Estatísticas, resultados e evolução da temporada regular em tempo real.")

df = load_nflverse_data(CURRENT_PFR_YEAR)
current_week = get_current_week() or df["Week"].max()

# ========== CLASSIFICAÇÃO ==========
st.markdown("<div class='section-title'>🏆 Classificação da Temporada</div>", unsafe_allow_html=True)
df_standings = calculate_standings(df)

col1, col2 = st.columns(2)
for conf, col in zip(["AFC","NFC"], [col1,col2]):
    with col:
        st.subheader(conf)
        df_conf = df_standings[df_standings["Conf"]==conf].sort_values("PCT", ascending=False)
        df_conf["Rank"] = range(1, len(df_conf)+1)
        st.dataframe(
            df_conf[["Rank","Team","W","L","T","PCT","Div"]],
            hide_index=True,
            use_container_width=True
        )

# ========== GRÁFICOS ==========
st.markdown("<div class='section-title'>📈 Estatísticas e Tendências</div>", unsafe_allow_html=True)

# Vitórias por Divisão
div_wins = df_standings.groupby(["Conf","Div"])["W"].sum().reset_index()
fig_div = px.bar(
    div_wins, x="Div", y="W", color="Conf", barmode="group",
    title="Vitórias Totais por Divisão", text_auto=True,
    color_discrete_map={"AFC":"#007bff","NFC":"#ff4d4d"}
)
fig_div.update_layout(xaxis_title="Divisão", yaxis_title="Vitórias", plot_bgcolor="#fafafa")
st.plotly_chart(fig_div, use_container_width=True)

# Evolução semanal das vitórias (top times)
weekly = df.groupby(["Week","Winner"]).size().reset_index(name="Wins")
weekly_sum = weekly.groupby(["Winner","Week"])["Wins"].sum().groupby(level=0).cumsum().reset_index()
top5 = df_standings.sort_values("W", ascending=False).head(5)["Team"].tolist()
weekly_sum = weekly_sum[weekly_sum["Winner"].isin(top5)]
fig_week = px.line(
    weekly_sum, x="Week", y="Wins", color="Winner",
    title="Evolução Semanal das Vitórias (Top 5 Times)"
)
fig_week.update_layout(xaxis=dict(dtick=1), yaxis_title="Vitórias Acumuladas", plot_bgcolor="#fafafa")
st.plotly_chart(fig_week, use_container_width=True)

# ========== HISTÓRICO ==========
st.markdown("<div class='section-title'>📅 Histórico de Jogos</div>", unsafe_allow_html=True)
week_select = st.selectbox("Selecione a semana:", sorted(df["Week"].unique()), index=current_week-1)
df_w = df[df["Week"]==week_select]

for _, r in df_w.iterrows():
    st.markdown(f"""
    <div class='data-card'>
        <b>Semana {r['Week']}</b> • {r['Date']}<br>
        🏆 <span style='color:#198754'>{r['Winner']}</span> {r['WinnerPts']} x {r['LoserPts']} {r['Loser']}
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><center><span class='subtext'>Fonte: NFLverse + ESPN API</span></center>", unsafe_allow_html=True)
