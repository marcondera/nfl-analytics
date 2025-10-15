import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="NFL Analytics Dashboard", layout="wide")

# ==============================
# 🎨 CSS personalizado
# ==============================
st.markdown("""
<style>
body {
    background-color: #0e1117;
    color: #fafafa;
    font-family: 'Roboto', sans-serif;
}
h1, h2, h3 {
    color: #00b4d8;
    font-weight: 700;
}
.card {
    background: linear-gradient(135deg, #1b1f27 0%, #212833 100%);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 15px;
    box-shadow: 0 0 15px rgba(0,0,0,0.3);
}
.card-title {
    font-size: 22px;
    font-weight: 600;
    color: #00b4d8;
    margin-bottom: 10px;
}
.score {
    font-size: 28px;
    font-weight: bold;
    color: #fff;
}
.team {
    font-size: 18px;
    font-weight: 500;
}
.winner {
    color: #21c55d;
    font-weight: 700;
}
table {
    border-collapse: collapse;
    width: 100%;
}
th, td {
    padding: 8px;
    text-align: left;
}
thead tr {
    background-color: #1f2937;
}
tbody tr:nth-child(even) {
    background-color: #111827;
}
</style>
""", unsafe_allow_html=True)

# ==============================
# 📡 Funções de dados
# ==============================
@st.cache_data(ttl=600)
def get_scores():
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    r = requests.get(url, timeout=10)
    data = r.json()
    games = []
    for event in data.get("events", []):
        game = {
            "date": datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
            "home": event["competitions"][0]["competitors"][0]["team"]["displayName"],
            "away": event["competitions"][0]["competitors"][1]["team"]["displayName"],
            "home_score": event["competitions"][0]["competitors"][0].get("score", 0),
            "away_score": event["competitions"][0]["competitors"][1].get("score", 0),
            "status": event["status"]["type"]["description"]
        }
        games.append(game)
    return pd.DataFrame(games)

@st.cache_data(ttl=600)
def get_standings():
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/standings"
    r = requests.get(url, timeout=10)
    data = r.json()
    teams = []
    for group in data.get("children", []):
        for div in group.get("children", []):
            for team in div.get("standings", {}).get("entries", []):
                info = team.get("team", {})
                record = team.get("stats", [])
                win = next((x["value"] for x in record if x["name"] == "wins"), 0)
                loss = next((x["value"] for x in record if x["name"] == "losses"), 0)
                pct = next((x["displayValue"] for x in record if x["name"] == "winPercent"), "-")
                teams.append({
                    "Conferência": group["name"],
                    "Divisão": div["name"],
                    "Time": info["displayName"],
                    "Vitórias": win,
                    "Derrotas": loss,
                    "Aproveitamento": pct
                })
    df = pd.DataFrame(teams)
    return df

# ==============================
# 📊 Placar da Semana
# ==============================
st.markdown("## 🏈 Placar da Semana")

try:
    df_scores = get_scores()
    if df_scores.empty:
        st.info("Nenhum jogo disponível no momento.")
    else:
        for _, row in df_scores.iterrows():
            home = row["home"]
            away = row["away"]
            hs = int(row["home_score"])
            as_ = int(row["away_score"])
            winner = home if hs > as_ else away if as_ > hs else None
            data_jogo = row["date"].strftime("%d %b %Y").lower()

            st.markdown(f"""
            <div class="card">
                <div class="card-title">{data_jogo} — {row["status"]}</div>
                <div class="team {'winner' if home==winner else ''}">{home}</div>
                <div class="score">{hs} - {as_}</div>
                <div class="team {'winner' if away==winner else ''}">{away}</div>
            </div>
            """, unsafe_allow_html=True)
except Exception as e:
    st.error(f"Erro ao carregar placares: {e}")

# ==============================
# 🏆 Classificação da Temporada
# ==============================
st.markdown("## 🏆 Classificação da Temporada")

try:
    df_standings = get_standings()
    if not df_standings.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### AFC")
            df_afc = df_standings[df_standings["Conferência"] == "AFC"]
            st.dataframe(df_afc.sort_values(["Vitórias", "Aproveitamento"], ascending=False),
                         hide_index=True, use_container_width=True)
        with col2:
            st.markdown("### NFC")
            df_nfc = df_standings[df_standings["Conferência"] == "NFC"]
            st.dataframe(df_nfc.sort_values(["Vitórias", "Aproveitamento"], ascending=False),
                         hide_index=True, use_container_width=True)
except Exception as e:
    st.error(f"Erro ao carregar classificação: {e}")

# ==============================
# 📜 Histórico de Jogos Recentes
# ==============================
st.markdown("## 📜 Histórico de Jogos Recentes")

try:
    if not df_scores.empty:
        historico = df_scores.sort_values("date", ascending=False).head(20).copy()
        historico["Data"] = historico["date"].dt.strftime("%d %b %Y").str.lower()
        historico["Placar"] = historico["away"] + " " + historico["away_score"].astype(str) + " × " + historico["home_score"].astype(str) + " " + historico["home"]
        historico = historico[["Data", "Placar", "status"]]
        st.dataframe(historico.rename(columns={"status": "Status"}), hide_index=True, use_container_width=True)
except Exception as e:
    st.error(f"Erro ao carregar histórico: {e}")
