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

# mapping for common variant fixes
COMMON_ABBR_FIXES = {
    "WAS": "WSH",
    "JAC": "JAX",
    "KAN": "KC",
    "KANZ": "KC",
    "LA": "LAR",   # ambiguous - pick LAR by default (could be LAC for Chargers)
    "LVR": "LV",
    "OAK": "LV"
}

MONTHS_PT = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
    7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"
}

# ========================
# APARÊNCIA / CSS
# ========================
def inject_css():
    st.markdown("""
    <style>
    body {font-family: 'Inter', sans-serif;}
    .big-title {font-size:2.0em;font-weight:800;color:#222;margin-bottom:8px;}
    .section-title {font-size:1.25em;font-weight:700;margin-top:20px;margin-bottom:8px;}
    .subtext {color:#6c757d;font-size:0.9em;}
    .metric-card {background:#fff;border-radius:12px;padding:12px;box-shadow:0 2px 6px rgba(0,0,0,0.04);text-align:center;}
    .data-card {background:#fff;border-radius:10px;padding:12px;margin-bottom:10px;border:1px solid #eef2f6;}
    .pfr-small {color:#64748b;font-size:12px;}
    </style>
    """, unsafe_allow_html=True)

inject_css()

# ========================
# UTILITÁRIAS
# ========================
def format_date_ptbr(date_str):
    """Tenta normalizar datas em formato yyyy-mm-dd ou ISO -> '09 out 2025'"""
    if not date_str or pd.isna(date_str):
        return ""
    try:
        # some gameday fields can be "2025-10-09" or "2025-10-09T00:00:00"
        date_part = str(date_str).split("T")[0]
        dt = datetime.strptime(date_part, "%Y-%m-%d")
        return f"{dt.day:02d} {MONTHS_PT[dt.month]} {dt.year}"
    except Exception:
        return str(date_str)

def normalize_team(raw):
    """
    Normaliza possíveis variações de identificação de time vindas do CSV.
    Retorna sigla padrão que exista em TEAM_CONFERENCE_DIVISION_MAP ou None.
    Estratégia:
    - Se já é uma sigla conhecida -> retorna.
    - Aplica correções comuns (COMMON_ABBR_FIXES).
    - Tenta uppercase + primeiros 3 chars.
    - Tenta últimos 3 chars.
    - Caso falhe, retorna None.
    """
    if raw is None:
        return None
    t = str(raw).strip().upper()
    if t in TEAM_CONFERENCE_DIVISION_MAP:
        return t
    # common fixes
    if t in COMMON_ABBR_FIXES:
        fixed = COMMON_ABBR_FIXES[t]
        if fixed in TEAM_CONFERENCE_DIVISION_MAP:
            return fixed
    # try first 3 chars
    if len(t) >= 3:
        first3 = t[:3]
        if first3 in TEAM_CONFERENCE_DIVISION_MAP:
            return first3
        # last 3
        last3 = t[-3:]
        if last3 in TEAM_CONFERENCE_DIVISION_MAP:
            return last3
    # try to remove non letters and retry
    only_letters = "".join(ch for ch in t if ch.isalpha())
    if len(only_letters) >= 3:
        if only_letters in TEAM_CONFERENCE_DIVISION_MAP:
            return only_letters
        if only_letters[:3] in TEAM_CONFERENCE_DIVISION_MAP:
            return only_letters[:3]
        if only_letters[-3:] in TEAM_CONFERENCE_DIVISION_MAP:
            return only_letters[-3:]
    return None

# ========================
# CARREGAMENTO DE DADOS
# ========================
@st.cache_data(ttl=3600)
def load_nflverse_data(year):
    """
    Retorna DataFrame com colunas:
    Week, Date (format pt-br), Winner, Loser, WinnerPts, LoserPts
    Winner/Loser já normalizados para siglas padrão quando possível.
    """
    try:
        raw = pd.read_csv(NFLVERSE_GAMES_URL)
    except Exception as e:
        st.error(f"Erro ao baixar CSV do NFLverse: {e}")
        return pd.DataFrame()

    # filtra por temporada e jogos regulares
    df = raw[(raw.get("season") == year) & (raw.get("game_type") == "REG")].copy()
    if df.empty:
        return pd.DataFrame()

    # converte scores para numerico
    df["home_score"] = pd.to_numeric(df.get("home_score", 0), errors="coerce").fillna(0).astype(int)
    df["away_score"] = pd.to_numeric(df.get("away_score", 0), errors="coerce").fillna(0).astype(int)

    rows = []
    for _, r in df.iterrows():
        try:
            week = int(r.get("week", 0))
        except Exception:
            continue
        # raw team identifiers (can be siglas ou nomes)
        raw_home = r.get("home_team") or r.get("home_team_id") or ""
        raw_away = r.get("away_team") or r.get("away_team_id") or ""

        home_score = int(r.get("home_score", 0))
        away_score = int(r.get("away_score", 0))

        # determine winner/loser by score
        if home_score >= away_score:
            raw_w, raw_l = raw_home, raw_away
            wp, lp = home_score, away_score
        else:
            raw_w, raw_l = raw_away, raw_home
            wp, lp = away_score, home_score

        w = normalize_team(raw_w)
        l = normalize_team(raw_l)

        # date
        gameday = r.get("gameday") or r.get("game_date") or ""
        date_fmt = format_date_ptbr(gameday)

        rows.append({
            "Week": week,
            "Date": date_fmt,
            "Winner_Raw": raw_w,
            "Loser_Raw": raw_l,
            "Winner": w,
            "Loser": l,
            "WinnerPts": wp,
            "LoserPts": lp,
        })

    return pd.DataFrame(rows)

@st.cache_data(ttl=600)
def get_current_week():
    try:
        data = requests.get(API_URL_SCOREBOARD, timeout=6).json()
        txt = data.get("week", {}).get("text", "")
        num = "".join(ch for ch in txt if ch.isdigit())
        return int(num) if num else None
    except Exception:
        return None

# ========================
# CÁLCULOS / GRÁFICOS
# ========================
def calculate_standings(df):
    """
    Calcula vitórias/derrotas/empates apenas para times reconhecidos.
    Retorna DataFrame com Abbr/Team/Conf/Div/W/L/T/GP/PCT.
    """
    # init table
    table = {abbr: {"W": 0, "L": 0, "T": 0} for abbr in TEAM_CONFERENCE_DIVISION_MAP.keys()}
    unknown_teams = set()

    for _, r in df.iterrows():
        w = r.get("Winner")
        l = r.get("Loser")
        # Se qualquer um for None (não reconhecido), registra e pula
        if not w or not l or w not in table or l not in table:
            # collect unknowns
            if w and w not in table:
                unknown_teams.add((w, r.get("Winner_Raw")))
            if l and l not in table:
                unknown_teams.add((l, r.get("Loser_Raw")))
            continue
        wp = int(r.get("WinnerPts", 0))
        lp = int(r.get("LoserPts", 0))
        if wp > lp:
            table[w]["W"] += 1
            table[l]["L"] += 1
        elif wp < lp:
            table[l]["W"] += 1
            table[w]["L"] += 1
        else:
            table[w]["T"] += 1
            table[l]["T"] += 1

    df_stand = pd.DataFrame.from_dict(table, orient="index").reset_index().rename(columns={"index": "Abbr"})
    df_stand["Team"] = df_stand["Abbr"]  # shorthand (sigla)
    df_stand["Conf"] = df_stand["Abbr"].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get("conf", "N/A"))
    df_stand["Div"] = df_stand["Abbr"].apply(lambda x: TEAM_CONFERENCE_DIVISION_MAP.get(x, {}).get("div", "N/A"))
    df_stand = df_stand[df_stand["Conf"] != "N/A"].copy()
    df_stand["GP"] = df_stand["W"] + df_stand["L"] + df_stand["T"]
    df_stand["PCT"] = df_stand.apply(lambda r: round((r["W"] + 0.5 * r["T"]) / r["GP"], 3) if r["GP"] > 0 else 0.0, axis=1)
    df_stand = df_stand.sort_values(by=["Conf", "PCT", "W"], ascending=[True, False, False]).reset_index(drop=True)

    return df_stand, unknown_teams

def wins_by_division_chart(df_stand):
    df = df_stand.groupby(["Conf", "Div"])["W"].sum().reset_index()
    fig = px.bar(df, x="Div", y="W", color="Conf", barmode="group", title="Vitórias Totais por Divisão", text_auto=True)
    fig.update_layout(plot_bgcolor="#fafafa", margin=dict(t=40, r=10, l=10, b=10))
    return fig

def weekly_evolution(df):
    # acumulado semanal por time (somente times reconhecidos)
    weekly = df.dropna(subset=["Winner"]).groupby(["Week", "Winner"]).size().reset_index(name="Wins")
    # pivot para acumular
    pivot = weekly.pivot(index="Week", columns="Winner", values="Wins").fillna(0).cumsum()
    return pivot

# ========================
# MAIN - INTERFACE
# ========================
st.markdown(f"<div class='big-title'>🏈 NFL Analytics {CURRENT_PFR_YEAR}</div>", unsafe_allow_html=True)
st.caption("Estatísticas, resultados e evolução da temporada regular (dados: NFLverse + ESPN)")

df = load_nflverse_data(CURRENT_PFR_YEAR)
if df.empty:
    st.error("Não foi possível carregar ou processar os dados históricos do NFLverse para esta temporada.")
    st.stop()

current_week = get_current_week() or int(df["Week"].max())

# calcular classificação
standings_df, unknowns = calculate_standings(df)

# Mostrar aviso sobre times desconhecidos (uma vez)
if unknowns:
    unknown_list = sorted({u[0] for u in unknowns})
    st.warning(f"Foram encontradas siglas/identificadores não reconhecidos e ignorados na contagem: {', '.join(unknown_list)}. Esses registros foram pulados para evitar inconsistências.")

# ========== CLASSIFICAÇÃO ==========
st.markdown("<div class='section-title'>🏆 Classificação da Temporada</div>", unsafe_allow_html=True)
afc = standings_df[standings_df["Conf"] == "AFC"].sort_values(["PCT", "W"], ascending=[False, False]).reset_index(drop=True)
nfc = standings_df[standings_df["Conf"] == "NFC"].sort_values(["PCT", "W"], ascending=[False, False]).reset_index(drop=True)

col1, col2 = st.columns(2)
with col1:
    st.subheader("AFC")
    if afc.empty:
        st.info("Sem dados da AFC.")
    else:
        afc_display = afc.copy()
        afc_display["Pos"] = range(1, len(afc_display) + 1)
        st.dataframe(afc_display[["Pos", "Abbr", "W", "L", "T", "GP", "PCT", "Div"]], hide_index=True, use_container_width=True)

with col2:
    st.subheader("NFC")
    if nfc.empty:
        st.info("Sem dados da NFC.")
    else:
        nfc_display = nfc.copy()
        nfc_display["Pos"] = range(1, len(nfc_display) + 1)
        st.dataframe(nfc_display[["Pos", "Abbr", "W", "L", "T", "GP", "PCT", "Div"]], hide_index=True, use_container_width=True)

# ========== GRÁFICOS ==========
st.markdown("<div class='section-title'>📈 Estatísticas & Tendências</div>", unsafe_allow_html=True)

col_g1, col_g2 = st.columns([1.4, 2])
with col_g1:
    st.markdown("**Vitórias por Divisão**")
    fig_div = wins_by_division_chart(standings_df)
    st.plotly_chart(fig_div, use_container_width=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    st.markdown("**Top - Total de Vitórias**")
    top_n = 8
    top_df = standings_df.sort_values(["W", "PCT"], ascending=[False, False]).head(top_n)
    if not top_df.empty:
        st.table(top_df[["Abbr", "W", "L", "T", "PCT"]].rename(columns={"Abbr": "Sigla"}))
    else:
        st.info("Sem líderes para exibir.")

with col_g2:
    st.markdown("**Evolução Semanal (acumulada)**")
    pivot = weekly_evolution(df)
    if pivot.empty:
        st.info("Dados insuficientes para evolução semanal.")
    else:
        # escolher até 5 times mais vencedores
        top_teams = standings_df.sort_values("W", ascending=False).head(5)["Abbr"].tolist()
        # filtrar colunas existentes no pivot
        existing = [t for t in top_teams if t in pivot.columns]
        if not existing:
            st.info("Nenhum dos top teams aparece na evolução semanal.")
        else:
            fig_week = px.line(pivot[existing].reset_index(), x="Week", y=existing, title="Vitórias acumuladas por semana (Top 5)")
            fig_week.update_layout(xaxis=dict(dtick=1), plot_bgcolor="#fafafa", margin=dict(t=40, r=10, l=10, b=10))
            st.plotly_chart(fig_week, use_container_width=True)

# ========== PLACAR - ÚLTIMA SEMANA ==========
st.markdown("<div class='section-title'>🗓️ Placar - Semana</div>", unsafe_allow_html=True)
weeks = sorted(df["Week"].unique())
default_idx = weeks.index(current_week) if current_week in weeks else len(weeks) - 1
sel_week = st.selectbox("Selecione a semana para exibir o placar:", weeks, index=default_idx)
df_week = df[df["Week"] == sel_week]

if df_week.empty:
    st.info("Nenhum jogo encontrado para a semana selecionada.")
else:
    cols = st.columns(3)
    games = df_week.to_dict("records")
    for i, g in enumerate(games):
        with cols[i % 3]:
            st.markdown(f"""
                <div class='data-card'>
                    <div style='display:flex;justify-content:space-between;align-items:center;'>
                        <div><b>Semana {g['Week']}</b></div>
                        <div class='pfr-small'>{g.get('Date','')}</div>
                    </div>
                    <div style='display:flex;justify-content:space-between;align-items:center;margin-top:10px'>
                        <div style='text-align:center'><div style='font-weight:800'>{g.get('Winner') or g.get('Winner_Raw')}</div></div>
                        <div style='text-align:center'><div style='font-size:18px;font-weight:900;color:#0ea5a4'>{int(g.get('WinnerPts',0))}</div><div style='font-weight:700;color:#475569'>VS</div><div style='font-size:16px;font-weight:700;color:#94a3b8'>{int(g.get('LoserPts',0))}</div></div>
                        <div style='text-align:center'><div style='font-weight:800'>{g.get('Loser') or g.get('Loser_Raw')}</div></div>
                    </div>
                    <div style='margin-top:8px;color:#64748b;font-size:13px'>{(g.get('Winner_Raw') or '')} venceu {(g.get('Loser_Raw') or '')}</div>
                </div>
            """, unsafe_allow_html=True)

# ========== HISTÓRICO ==========
st.markdown("<div class='section-title'>📅 Histórico de Jogos (detalhado)</div>", unsafe_allow_html=True)
if st.checkbox("Mostrar tabela completa de resultados (raw)"):
    display_df = df[["Week", "Date", "Winner_Raw", "Winner", "WinnerPts", "Loser_Raw", "Loser", "LoserPts"]].rename(columns={
        "Week": "Semana", "Date": "Data", "Winner_Raw": "Vencedor (raw)", "Winner": "Vencedor (sigla)",
        "WinnerPts": "Vencedor Pts", "Loser_Raw": "Perdedor (raw)", "Loser": "Perdedor (sigla)", "LoserPts": "Perdedor Pts"
    })
    st.dataframe(display_df, use_container_width=True)

st.markdown("<br><center><span class='subtext'>Obs: alguns registros do CSV podem ter identificadores não-padrão — esses foram ignorados na contagem para evitar erros. Fonte: NFLverse + ESPN API</span></center>", unsafe_allow_html=True)
