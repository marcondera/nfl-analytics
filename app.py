import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# -----------------------------------------------------------
# 🔧 CONFIGURAÇÕES GERAIS
# -----------------------------------------------------------
st.set_page_config(page_title="NFL Dashboard 2025", layout="wide", page_icon="🏈")

CURRENT_PFR_YEAR = 2025
NFLVERSE_GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
API_URL_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# -----------------------------------------------------------
# 🧠 MAPEAMENTOS BÁSICOS
# -----------------------------------------------------------
LOGO_MAP = {
    "BUF": "buf", "MIA": "mia", "NYJ": "nyj", "NE": "ne",
    "BAL": "bal", "CIN": "cin", "CLE": "cle", "PIT": "pit",
    "HOU": "hou", "IND": "ind", "JAX": "jax", "TEN": "ten",
    "DEN": "den", "KC": "kc", "LV": "lv", "LAC": "lac",
    "DAL": "dal", "NYG": "nyg", "PHI": "phi", "WAS": "wsh",
    "CHI": "chi", "DET": "det", "GB": "gb", "MIN": "min",
    "ATL": "atl", "CAR": "car", "NO": "no", "TB": "tb",
    "ARI": "ari", "LA": "lar", "SF": "sf", "SEA": "sea"
}

PFR_NAME_MAP_REVERSE = {
    "BUF": "Buffalo Bills", "MIA": "Miami Dolphins", "NYJ": "New York Jets", "NE": "New England Patriots",
    "BAL": "Baltimore Ravens", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "PIT": "Pittsburgh Steelers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars", "TEN": "Tennessee Titans",
    "DEN": "Denver Broncos", "KC": "Kansas City Chiefs", "LV": "Las Vegas Raiders", "LAC": "Los Angeles Chargers",
    "DAL": "Dallas Cowboys", "NYG": "New York Giants", "PHI": "Philadelphia Eagles", "WAS": "Washington Commanders",
    "CHI": "Chicago Bears", "DET": "Detroit Lions", "GB": "Green Bay Packers", "MIN": "Minnesota Vikings",
    "ATL": "Atlanta Falcons", "CAR": "Carolina Panthers", "NO": "New Orleans Saints", "TB": "Tampa Bay Buccaneers",
    "ARI": "Arizona Cardinals", "LA": "Los Angeles Rams", "SF": "San Francisco 49ers", "SEA": "Seattle Seahawks"
}

TEAM_CONFERENCE_DIVISION_MAP = {
    "BUF": ("AFC", "East"), "MIA": ("AFC", "East"), "NYJ": ("AFC", "East"), "NE": ("AFC", "East"),
    "BAL": ("AFC", "North"), "CIN": ("AFC", "North"), "CLE": ("AFC", "North"), "PIT": ("AFC", "North"),
    "HOU": ("AFC", "South"), "IND": ("AFC", "South"), "JAX": ("AFC", "South"), "TEN": ("AFC", "South"),
    "DEN": ("AFC", "West"), "KC": ("AFC", "West"), "LV": ("AFC", "West"), "LAC": ("AFC", "West"),
    "DAL": ("NFC", "East"), "NYG": ("NFC", "East"), "PHI": ("NFC", "East"), "WAS": ("NFC", "East"),
    "CHI": ("NFC", "North"), "DET": ("NFC", "North"), "GB": ("NFC", "North"), "MIN": ("NFC", "North"),
    "ATL": ("NFC", "South"), "CAR": ("NFC", "South"), "NO": ("NFC", "South"), "TB": ("NFC", "South"),
    "ARI": ("NFC", "West"), "LA": ("NFC", "West"), "SF": ("NFC", "West"), "SEA": ("NFC", "West")
}

# -----------------------------------------------------------
# 🎨 ESTILO
# -----------------------------------------------------------
def inject_custom_css():
    st.markdown("""
    <style>
    .score-card {
        background: #f9f9f9;
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 0 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    .winner { color: #198754; font-weight: bold; }
    .loser { color: #6c757d; }
    .status { font-size: 0.8em; color: #999; margin-top: 4px; }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# -----------------------------------------------------------
# 📦 FUNÇÕES DE DADOS
# -----------------------------------------------------------
@st.cache_data(ttl=3600)
def load_historical_events_from_nflverse():
    df = pd.read_csv(NFLVERSE_GAMES_URL)
    df = df[df['season'] == CURRENT_PFR_YEAR].copy()
    df = df[["week", "game_date", "home_team", "away_team", "home_score", "away_score"]]
    df.rename(columns={"week": "Week"}, inplace=True)
    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce")
    # Não filtra por pontuação — permite jogos ainda não finalizados
    return df

@st.cache_data(ttl=600)
def load_live_events_from_espn():
    response = requests.get(API_URL_SCOREBOARD)
    data = response.json()
    current_week = data.get("week", {}).get("number", None)
    events = data.get("events", [])
    return current_week, events

def get_logo_url(team_abbr):
    if team_abbr not in LOGO_MAP:
        return ""
    code = LOGO_MAP[team_abbr]
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{code}.png"

# -----------------------------------------------------------
# 🏈 EXIBIÇÃO DOS JOGOS
# -----------------------------------------------------------
def display_scoreboard(df_pfr, current_week, events):
    st.header(f"📅 Semana Atual: {current_week}")

    df_week = df_pfr[df_pfr["Week"] == current_week].copy()

    # Se ainda não há dados históricos — mostrar agendados
    if df_week.empty:
        st.info(f"ℹ️ A semana {current_week} ainda está em andamento. Mostrando jogos agendados:")
        display_future_games(events)
        return

    cols = st.columns(3)
    for i, (_, row) in enumerate(df_week.iterrows()):
        home, away = row["home_team"], row["away_team"]
        home_score = row["home_score"]
        away_score = row["away_score"]
        date = row["game_date"].strftime("%d/%m")

        home_logo = get_logo_url(home)
        away_logo = get_logo_url(away)

        result_home = ""
        result_away = ""
        if pd.notna(home_score) and pd.notna(away_score):
            if home_score > away_score:
                result_home = "winner"
                result_away = "loser"
            elif home_score < away_score:
                result_home = "loser"
                result_away = "winner"

        with cols[i % 3]:
            st.markdown(f"""
            <div class="score-card">
                <img src="{away_logo}" width="40"> <span class="{result_away}">{away_score if pd.notna(away_score) else '-'}</span>
                <br>
                <img src="{home_logo}" width="40"> <span class="{result_home}">{home_score if pd.notna(home_score) else '-'}</span>
                <div class="status">{date}</div>
            </div>
            """, unsafe_allow_html=True)

def display_future_games(events):
    if not events:
        st.warning("Nenhum jogo futuro encontrado na API ESPN.")
        return
    cols = st.columns(3)
    for i, e in enumerate(events):
        comp = e.get("competitions", [{}])[0]
        competitors = comp.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        home_team = home.get("team", {}).get("abbreviation", "???")
        away_team = away.get("team", {}).get("abbreviation", "???")
        date = datetime.fromisoformat(comp.get("date").replace("Z", "+00:00")).strftime("%d/%m %H:%M")
        home_logo = get_logo_url(home_team)
        away_logo = get_logo_url(away_team)

        with cols[i % 3]:
            st.markdown(f"""
            <div class="score-card">
                <img src="{away_logo}" width="40"> @ <img src="{home_logo}" width="40">
                <div class="status">Agendado: {date}</div>
            </div>
            """, unsafe_allow_html=True)

# -----------------------------------------------------------
# 🧮 CLASSIFICAÇÃO
# -----------------------------------------------------------
def calculate_standings(df):
    df_results = df.dropna(subset=["home_score", "away_score"]).copy()
    standings = {}
    for _, row in df_results.iterrows():
        home, away = row["home_team"], row["away_team"]
        hs, as_ = row["home_score"], row["away_score"]
        if home not in standings:
            standings[home] = {"W": 0, "L": 0, "T": 0}
        if away not in standings:
            standings[away] = {"W": 0, "L": 0, "T": 0}
        if hs > as_:
            standings[home]["W"] += 1
            standings[away]["L"] += 1
        elif hs < as_:
            standings[home]["L"] += 1
            standings[away]["W"] += 1
        else:
            standings[home]["T"] += 1
            standings[away]["T"] += 1
    df_stand = pd.DataFrame([
        {"Team": t, **rec, "PCT": (rec["W"] + 0.5 * rec["T"]) / max(1, rec["W"] + rec["L"] + rec["T"])}
        for t, rec in standings.items()
    ])
    df_stand["Conference"] = df_stand["Team"].map(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, ("", ""))[0])
    df_stand["Division"] = df_stand["Team"].map(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, ("", ""))[1])
    return df_stand.sort_values(["Conference", "Division", "PCT"], ascending=[True, True, False])

def display_standings(df_stand):
    st.header("🏆 Classificação")
    for conf in ["AFC", "NFC"]:
        st.subheader(f"{conf}")
        conf_df = df_stand[df_stand["Conference"] == conf]
        st.dataframe(conf_df[["Team", "W", "L", "T", "PCT", "Division"]], use_container_width=True)

# -----------------------------------------------------------
# 🚀 MAIN
# -----------------------------------------------------------
def main():
    st.title("🏈 NFL Dashboard 2025")

    df_pfr = load_historical_events_from_nflverse()
    current_week, events = load_live_events_from_espn()

    if not current_week:
        st.error("Não foi possível obter a semana atual da ESPN.")
        return

    display_scoreboard(df_pfr, current_week, events)
    df_stand = calculate_standings(df_pfr)
    display_standings(df_stand)

if __name__ == "__main__":
    main()
