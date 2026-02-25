"""
Hoops Edge — Premium Streamlit Dashboard
Run with: streamlit run src/ui/app.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import asyncio
import streamlit as st
import json
from datetime import datetime
from typing import Optional

from src.db.storage import BetLedger
from src.tools.odds_client import get_live_games
from src.agents.ev_calculator import analyze_full_slate
from src.tools.espn_client import (
    fetch_team_summary, fetch_team_roster, fetch_team_schedule,
    fetch_best_worst, fetch_boxscore, fetch_player_stats,
    fetch_team_stat_leaders, fetch_game_venue, inches_to_ft,
    get_espn_team_id, logo_url, TEAM_ESPN_IDS, get_all_espn_teams
)

def generate_matchup_bullets(g, tip: str) -> str:
    """Generate HTML bullet points comparing teams for game preview cards and search results."""
    away_name = g.away_team
    home_name = g.home_team
    away_oe = g.away_stats.offensive_efficiency if g.away_stats else None
    home_de = g.home_stats.defensive_efficiency if g.home_stats else None
    away_de = g.away_stats.defensive_efficiency if g.away_stats else None
    home_oe = g.home_stats.offensive_efficiency if g.home_stats else None
    
    bullets = []
    if away_oe and home_de:
        bullets.append(f"• <b>{away_name.split()[0]} Offense</b>: OE {away_oe:.0f} vs <b>{home_name.split()[0]} Defense</b>: DE {home_de:.0f}")
    if home_oe and away_de:
        bullets.append(f"• <b>{home_name.split()[0]} Offense</b>: OE {home_oe:.0f} vs <b>{away_name.split()[0]} Defense</b>: DE {away_de:.0f}")
        
    if g.away_stats and g.home_stats:
        if g.away_stats.pace and g.home_stats.pace:
            avg_pace = (g.away_stats.pace + g.home_stats.pace) / 2
            if avg_pace > 70:
                bullets.append(f"• <b>Pace</b>: Up-tempo showcase (~{avg_pace:.0f} poss)")
            elif avg_pace < 66:
                bullets.append(f"• <b>Pace</b>: Low-scoring grind (~{avg_pace:.0f} poss)")
        
        away_ats = g.away_stats.ats_record
        home_ats = g.home_stats.ats_record
        if away_ats or home_ats:
            ats_str = "• <b>Against the Spread</b>: "
            if away_ats: ats_str += f"{away_name.split()[0]} ({away_ats})"
            if away_ats and home_ats: ats_str += " | "
            if home_ats: ats_str += f"{home_name.split()[0]} ({home_ats})"
            bullets.append(ats_str)
            
        away_3pr = g.away_stats.three_point_rate
        home_3pr = g.home_stats.three_point_rate
        if away_3pr or home_3pr:
            thr_str = "• <b>3-Point Reliance</b>: "
            if away_3pr: 
                sz = "High" if away_3pr > 0.40 else ("Low" if away_3pr < 0.32 else "Avg")
                thr_str += f"{away_name.split()[0]} ({sz} {away_3pr*100:.0f}%)"
            if away_3pr and home_3pr: 
                thr_str += " | "
            if home_3pr: 
                sz = "High" if home_3pr > 0.40 else ("Low" if home_3pr < 0.32 else "Avg")
                thr_str += f"{home_name.split()[0]} ({sz} {home_3pr*100:.0f}%)"
            bullets.append(thr_str)
    
    if not bullets:
        bullets.append(f"• Tipping off at {tip} — check back closer to tip for stats.")
        
    return "<br>".join(bullets)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hoops Edge",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design System ──────────────────────────────────────────────────────────────
COLORS = {
    "bg":        "#080c14",
    "surface":   "#111827",
    "surface2":  "#1a2236",
    "border":    "#1e2d45",
    "accent":    "#f97316",
    "gold":      "#fbbf24",
    "green":     "#22c55e",
    "red":       "#ef4444",
    "muted":     "#6b7280",
    "text":      "#f1f5f9",
    "text2":     "#94a3b8",
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif !important;
    background-color: {COLORS["bg"]} !important;
    color: {COLORS["text"]} !important;
}}

.stApp {{ background-color: {COLORS["bg"]} !important; }}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0d1424 0%, #0a1020 100%) !important;
    border-right: 1px solid {COLORS["border"]};
    transition: transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1), width 0.35s cubic-bezier(0.2, 0.8, 0.2, 1), transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1) !important;
}}
[data-testid="collapsedControl"] {{
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: {COLORS["surface"]} !important;
    border: 1px solid {COLORS["border"]} !important;
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    margin-top: 10px !important;
    margin-left: 10px !important;
    transition: transform 0.2s ease, background 0.2s ease !important;
    z-index: 999999 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5) !important;
}}
[data-testid="collapsedControl"]:hover {{
    background: {COLORS["surface2"]} !important;
    transform: scale(1.1) !important;
}}
[data-testid="collapsedControl"] svg {{
    fill: {COLORS["accent"]} !important;
    width: 18px !important;
    height: 18px !important;
}}

[data-testid="stSidebar"] .stButton > button {{
    width: 100%;
    background: transparent;
    border: 1px solid transparent;
    color: {COLORS["text2"]};
    border-radius: 10px;
    padding: 0.6rem 1rem;
    text-align: left;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s ease;
    margin-bottom: 4px;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: {COLORS["surface2"]};
    border-color: {COLORS["border"]};
    color: {COLORS["text"]};
}}
.nav-active > div > button {{
    background: linear-gradient(90deg, #f97316 0%, #fb923c 100%) !important;
    border-color: transparent !important;
    color: white !important;
    font-weight: 700 !important;
}}

/* ── Glass Cards ── */
.glass-card {{
    background: linear-gradient(135deg, rgba(26,34,54,0.9) 0%, rgba(17,24,39,0.95) 100%);
    border: 1px solid {COLORS["border"]};
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(12px);
    transition: transform 0.2s ease, border-color 0.2s ease;
}}
.glass-card:hover {{ border-color: #2d4a6e; transform: translateY(-1px); }}
.glass-card.accent  {{ border-left: 4px solid {COLORS["accent"]}; }}
.glass-card.green   {{ border-left: 4px solid {COLORS["green"]}; }}
.glass-card.gold    {{ border-left: 4px solid {COLORS["gold"]}; }}
.glass-card.red     {{ border-left: 4px solid {COLORS["red"]}; }}

/* ── Hero ── */
.hero {{
    background: linear-gradient(135deg, #0f172a 0%, #1e1035 50%, #0f172a 100%);
    border: 1px solid {COLORS["border"]};
    border-radius: 20px;
    padding: 2.5rem 2rem;
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}}
.hero::before {{
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(249,115,22,0.08) 0%, transparent 60%);
    animation: pulse 4s ease-in-out infinite;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 0.6; transform: scale(0.95); }}
    50%       {{ opacity: 1;   transform: scale(1.05); }}
}}
.hero h1 {{
    font-size: 3rem;
    font-weight: 900;
    background: linear-gradient(135deg, #f97316 0%, #fbbf24 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    letter-spacing: -1px;
}}
.hero p {{ color: {COLORS["text2"]}; font-size: 1.1rem; margin: 0.5rem 0 0; }}

/* ── Stat tiles ── */
.stat-tile {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
    padding: 1.2rem;
    text-align: center;
}}
.stat-tile .val {{
    font-size: 2rem;
    font-weight: 800;
    color: {COLORS["accent"]};
    line-height: 1;
}}
.stat-tile .lbl {{
    font-size: 0.75rem;
    color: {COLORS["muted"]};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.3rem;
}}

/* ── Badge ── */
.badge {{
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.03em;
}}
.badge-green  {{ background: rgba(34,197,94,0.15); color: #22c55e; }}
.badge-yellow {{ background: rgba(251,191,36,0.15); color: #fbbf24; }}
.badge-red    {{ background: rgba(239,68,68,0.15); color: #ef4444; }}
.badge-blue   {{ background: rgba(59,130,246,0.15); color: #60a5fa; }}
.badge-orange {{ background: rgba(249,115,22,0.15); color: #f97316; }}

/* ── Page title ── */
.page-title {{
    font-size: 1.6rem;
    font-weight: 800;
    color: {COLORS["text"]};
    margin-bottom: 0.2rem;
}}
.page-sub {{
    font-size: 0.9rem;
    color: {COLORS["muted"]};
    margin-bottom: 1.5rem;
}}

/* ── Chat search ── */
[data-testid="stChatInput"] > div {{
    background: {COLORS["surface"]} !important;
    border: 1px solid {COLORS["border"]} !important;
    border-radius: 12px !important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: {COLORS["bg"]}; }}
::-webkit-scrollbar-thumb {{ background: {COLORS["border"]}; border-radius: 3px; }}

/* ── Hide streamlit branding ── */
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar Toggle Buttons (Collapse / Expand) ── */
button[kind="headerNoPadding"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: {COLORS["surface"]} !important;
    border: 1px solid {COLORS["border"]} !important;
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    margin-top: 10px !important;
    margin-left: 10px !important;
    transition: transform 0.2s ease, background 0.2s ease !important;
    z-index: 999999 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5) !important;
    color: {COLORS["accent"]} !important;
}
button[kind="headerNoPadding"]:hover {
    background: {COLORS["surface2"]} !important;
    transform: scale(1.1) !important;
}
button[kind="headerNoPadding"] svg {
    fill: {COLORS["accent"]} !important;
    color: {COLORS["accent"]} !important;
    width: 18px !important;
    height: 18px !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 0.8rem 1rem;
}}

/* ── Buttons ── */
.stButton > button {{
    border-radius: 10px;
    font-weight: 600;
    transition: all 0.2s ease;
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, #f97316 0%, #ea730e 100%) !important;
    border: none !important;
    color: white !important;
}}
.stButton > button[kind="primary"]:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 20px rgba(249,115,22,0.3);
}}

/* ── Divider ── */
hr {{ border-color: {COLORS["border"]} !important; }}

/* ══ INDIE VIBE HOME ══ */
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap');

/* Indie hero */
.indie-hero {{
    background: linear-gradient(135deg, #1a0533 0%, #0d1f3c 40%, #0a2a1a 100%);
    border-radius: 24px;
    padding: 3rem 2rem 2.5rem;
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.06);
}}
.indie-hero::before {{
    content: '';
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse at 20% 50%, rgba(255,105,180,.18) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 30%, rgba(64,224,208,.16) 0%, transparent 45%),
        radial-gradient(ellipse at 60% 80%, rgba(147,112,219,.14) 0%, transparent 45%);
    pointer-events: none;
}}
.indie-title {{
    font-family: 'Nunito', sans-serif;
    font-weight: 900;
    font-size: 3rem;
    background: linear-gradient(135deg, #ff6eb4 0%, #40e0d0 50%, #b48aff 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 .5rem;
    letter-spacing: -1px;
    animation: float 4s ease-in-out infinite;
}}
@keyframes float {{
    0%,100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-6px); }}
}}
.indie-sub {{
    font-family: 'Nunito', sans-serif;
    font-size: 1.05rem;
    font-weight: 600;
    color: rgba(255,255,255,.55);
    letter-spacing: .02em;
    margin-bottom: .4rem;
}}
.indie-date {{
    font-family: 'Nunito', sans-serif;
    font-size: .82rem;
    color: rgba(255,255,255,.28);
    letter-spacing: .06em;
}}

/* Stat pills */
.indie-stat {{
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.09);
    border-radius: 20px;
    padding: 1.1rem 1rem;
    text-align: center;
    transition: transform .2s, box-shadow .2s;
}}
.indie-stat:hover {{ transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,.3); }}
.indie-stat-val {{
    font-family: 'Nunito', sans-serif;
    font-size: 1.8rem;
    font-weight: 900;
    line-height: 1;
    margin-bottom: .3rem;
}}
.indie-stat-lbl {{
    font-family: 'Nunito', sans-serif;
    font-size: .7rem;
    font-weight: 700;
    color: rgba(255,255,255,.35);
    letter-spacing: .1em;
    text-transform: uppercase;
}}

/* Action section header */
.indie-section-hdr {{
    font-family: 'Nunito', sans-serif;
    font-size: 1rem;
    font-weight: 800;
    color: rgba(255,255,255,.45);
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: 1rem;
}}

/* Full-card Streamlit buttons — keys home_slate / home_pending / home_search */
[data-testid="stButton"] > button[kind="secondary"].indie-card {{
    width: 100%;
}}
/* Target by aria-label (key) */
div[data-testid="stButton"]:has(button[key="home_slate"]) button,
div[data-testid="stButton"]:has(button[key="home_pending"]) button,
div[data-testid="stButton"]:has(button[key="home_search"]) button,
div[data-testid="stButton"]:has(button[key="home_picks"]) button,
div[data-testid="stButton"]:has(button[key="home_teams"]) button,
div[data-testid="stButton"]:has(button[key="home_history"]) button {{
    width: 100%;
    height: auto;
    min-height: 130px;
    background: rgba(255,255,255,.04) !important;
    border: 1px solid rgba(255,255,255,.1) !important;
    border-radius: 20px !important;
    color: white !important;
    font-family: 'Nunito', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    white-space: pre-wrap !important;
    line-height: 1.5 !important;
    padding: 1.5rem 1.6rem !important;
    text-align: left !important;
    min-height: 160px !important;
    transition: transform .22s cubic-bezier(.34,1.56,.64,1), box-shadow .22s ease, border-color .18s, background .18s !important;
}}
div[data-testid="stButton"]:has(button[key="home_slate"]) button:hover,
div[data-testid="stButton"]:has(button[key="home_pending"]) button:hover,
div[data-testid="stButton"]:has(button[key="home_search"]) button:hover,
div[data-testid="stButton"]:has(button[key="home_picks"]) button:hover,
div[data-testid="stButton"]:has(button[key="home_teams"]) button:hover,
div[data-testid="stButton"]:has(button[key="home_history"]) button:hover {{
    transform: translateY(-8px) scale(1.02) !important;
    box-shadow: 0 20px 48px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.14) !important;
    background: rgba(255,255,255,.09) !important;
    border-color: rgba(255,255,255,.28) !important;
}}
/* Slate game cards */
.game-card {{
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 18px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1.1rem;
}}
.gc-teams {{ display:flex; align-items:center; gap:1.2rem; margin-bottom:.8rem; }}
.gc-team {{ display:flex; flex-direction:column; align-items:center; min-width:100px; gap:.25rem; }}
.gc-team img {{ border-radius:8px; }}
.gc-rank {{ font-family:'Nunito',sans-serif; font-size:.65rem; font-weight:800; color:#fbbf24; }}
.gc-tname {{ font-family:'Nunito',sans-serif; font-weight:800; font-size:.85rem; text-align:center; color:#f1f5f9; line-height:1.25; }}
.gc-rec {{ font-size:.72rem; color:#6b7280; font-weight:600; }}
.gc-label {{ font-size:.62rem; color:#4b5563; font-weight:700; letter-spacing:.06em; text-transform:uppercase; }}
.gc-vs {{ font-family:'Nunito'; font-size:1rem; font-weight:900; color:#374151; padding:0 .5rem; }}
.gc-mid {{ flex:1; display:flex; flex-direction:column; gap:.4rem; }}
.gc-venue {{ font-size:.75rem; color:#60a5fa; font-weight:600; }}
.gc-spread {{ font-size:.75rem; color:#a3e635; font-weight:700; }}
.gc-leaders {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.3rem; }}
.gc-pill {{ background:rgba(255,255,255,.06); border-radius:7px; padding:.2rem .55rem; font-size:.7rem; color:#d1d5db; }}
.gc-pill b {{ color:#f97316; }}
.gc-blurb {{ background:rgba(96,165,250,.06); border:1px solid rgba(96,165,250,.12); border-radius:12px; padding:.85rem 1rem; font-size:.81rem; color:#cbd5e1; line-height:1.5; margin-top:.6rem; }}
</style>
""", unsafe_allow_html=True)


# ── Shared state / helpers ─────────────────────────────────────────────────────
@st.cache_resource
def get_ledger():
    return BetLedger()

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def init_state(defaults: dict):
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def ev_badge(ev: float) -> str:
    pct = f"{ev:+.1%}"
    if ev >= 0.05:
        return f'<span class="badge badge-green">🔥 {pct}</span>'
    elif ev >= 0.035:
        return f'<span class="badge badge-yellow">⚡ {pct}</span>'
    return f'<span class="badge badge-red">{pct}</span>'

def card_class(ev: float) -> str:
    if ev >= 0.05:  return "glass-card green"
    if ev >= 0.035: return "glass-card gold"
    return "glass-card red"

def back_btn(dest: str = "home", label: str = "← Home"):
    """Render a small back-navigation button at the top of any non-home page."""
    if st.button(label, key=f"back_{dest}_{st.session_state.page}"):
        st.session_state.page = dest
        st.rerun()
    st.markdown("<div style='margin-bottom:.6rem'></div>", unsafe_allow_html=True)


ledger = get_ledger()
init_state({
    "page": "home",
    "slate": None,
    "slate_error": None,
    "all_games": None,
    "selected_ids": [],
    "search_messages": [],
})


# ── Sidebar navigation ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding: 1rem 0 0.5rem; text-align:center;">
  <span style="font-size:2.2rem">🏀</span>
  <div style="font-size:1.2rem; font-weight:900; letter-spacing:-0.5px;
              background:linear-gradient(135deg,#f97316,#fbbf24);
              -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
    Hoops Edge
  </div>
  <div style="font-size:0.7rem; color:#6b7280; letter-spacing:0.1em; text-transform:uppercase;">
    CBB +EV Agent
  </div>
</div>
""", unsafe_allow_html=True)
    st.markdown("---")

    def nav_btn(icon, label, page_key):
        active = st.session_state.page == page_key
        col = st.container()
        with col:
            if active:
                st.markdown('<div class="nav-active">', unsafe_allow_html=True)
            if st.button(f"{icon}  {label}", key=f"nav_{page_key}"):
                st.session_state.page = page_key
                st.rerun()
            if active:
                st.markdown("</div>", unsafe_allow_html=True)

    nav_btn("🏠", "Home", "home")
    nav_btn("📋", "Today's Slate", "slate")
    nav_btn("📊", "Picks & Analysis", "picks")
    nav_btn("⏳", "Pending Bets", "pending")
    nav_btn("📈", "Performance", "history")
    nav_btn("🏀", "Teams", "teams")
    nav_btn("🔍", "Game Search", "search")

    st.markdown("---")

    # Quick bankroll
    bankroll = ledger.get_bankroll()
    settled = list(ledger.db["bets"].rows_where("status = ?", ["settled"]))
    settled_parlays = list(ledger.db["parlays"].rows_where("status = ?", ["settled"]))
    wins   = sum(1 for b in settled if b["result"] == "win") + sum(1 for p in settled_parlays if p["result"] == "win")
    losses = sum(1 for b in settled if b["result"] == "loss") + sum(1 for p in settled_parlays if p["result"] == "loss")
    total_pl = sum(b["profit_loss"] for b in settled if b["profit_loss"] is not None) + \
               sum(p["profit_loss"] for p in settled_parlays if p["profit_loss"] is not None)
    pl_color = "#22c55e" if total_pl >= 0 else "#ef4444"

    st.markdown(f"""
<div style="background:{COLORS['surface']}; border:1px solid {COLORS['border']};
            border-radius:12px; padding:1rem; margin-top:0.5rem;">
  <div style="font-size:0.7rem;color:#6b7280;text-transform:uppercase;letter-spacing:.08em">Bankroll</div>
  <div style="font-size:1.6rem;font-weight:900;color:#f97316">{bankroll['balance_units']:.1f}u</div>
  <div style="font-size:0.8rem;color:{pl_color};margin-top:0.2rem">
    {"▲" if total_pl >= 0 else "▼"} {abs(total_pl):.2f}u all-time
  </div>
  <div style="font-size:0.8rem;color:#6b7280;margin-top:0.2rem">{wins}W – {losses}L</div>
</div>
""", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.7rem;color:#4b5563;text-align:center;margin-top:0.8rem'>{datetime.now().strftime('%b %d, %Y · %I:%M %p')}</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":
    today = datetime.now().strftime("%A, %B %d %Y")
    pending_bets = list(ledger.db["bets"].rows_where("status IN ('pending','approved')", []))
    pending_parlays = ledger.get_pending_parlays()
    total_pending = len(pending_bets) + len(pending_parlays)
    ev_bets = [b for b in pending_bets if b["status"] == "approved"]
    pl_sign = "+" if total_pl >= 0 else ""

    # ── INDIE HERO ──────────────────────────────────────────────
    st.markdown(f"""
<div class="indie-hero">
  <div class="indie-title">🏀 Hoops Edge</div>
  <div class="indie-sub">AI-Powered College Basketball Edge Detection</div>
  <div class="indie-date">{today}</div>
</div>
""", unsafe_allow_html=True)

    # ── STAT PILLS ──────────────────────────────────────────────
    pv_color = "#4ade80" if total_pl >= 0 else "#f87171"
    c1, c2, c3, c4 = st.columns(4)
    stat_defs = [
        (c1, f"{bankroll['balance_units']:.0f}u", "Bankroll",  "linear-gradient(135deg,#ff6eb4,#ff9a5c)"),
        (c2, f"{wins}–{losses}",                 "Record",    "linear-gradient(135deg,#40e0d0,#60a5fa)"),
        (c3, str(total_pending),                 "Pending",   "linear-gradient(135deg,#b48aff,#ff6eb4)"),
        (c4, f"{pl_sign}{total_pl:.1f}u",         "P / L",     f"linear-gradient(135deg,{pv_color},{pv_color}aa)"),
    ]
    for col, val, lbl, grad in stat_defs:
        with col:
            st.markdown(f"""
<div class="indie-stat">
  <div class="indie-stat-val" style="background:{grad};-webkit-background-clip:text;
       -webkit-text-fill-color:transparent;background-clip:text">{val}</div>
  <div class="indie-stat-lbl">{lbl}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="indie-section-hdr">✨ Quick Actions</div>', unsafe_allow_html=True)

    # ── FULL-CARD CLICKABLE BUTTONS ──────────────────────────────
    # Use st.button with multi-line label — styled via CSS into full card
    # 2-row layout with 3 cols each + 1 row with 1 col for Parlays
    row1 = st.columns(3)
    row2 = st.columns(3)
    row3 = st.columns([1,2,1]) # centering the parlay button
    actions = [
        (row1[0], "home_slate",   "slate",   "📋", "Today's Slate",   "Live lines → Pick games → Find edges"),
        (row1[1], "home_picks",   "picks",   "📊", "Picks & Analysis","See all AI bet suggestions"),
        (row1[2], "home_pending", "pending", "⏳", "Pending Bets",   f"{total_pending} ticket(s) awaiting action"),
        (row2[0], "home_search",  "search",  "🔍", "Game Search",    "Odds by team or conference"),
        (row2[1], "home_teams",   "teams",   "🏀", "Teams Explorer", "Roster, schedule & scouting reports"),
        (row2[2], "home_history", "history", "📈", "Performance",    "Bankroll history & settled bets"),
        (row3[1], "home_parlays", "parlays", "🔗", "Parlay Builder", "Combine approved bets for bigger payouts"),
    ]
    for col, key, pg, icon, title, desc in actions:
        with col:
            label = f"{icon}  {title}\n{desc}"
            if st.button(label, key=key, use_container_width=True):
                st.session_state.page = pg
                st.rerun()

    if ev_bets:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="page-title" style="font-size:1.1rem">🟢 Approved Bets Awaiting Result</div>', unsafe_allow_html=True)
        for b in ev_bets[:3]:
            st.markdown(f"""<div class="glass-card green" style="padding:.9rem 1.2rem">
              <span style="font-weight:700">{b['away_team']} @ {b['home_team']}</span>
              &nbsp;·&nbsp; {b['bet_type'].upper()} {b['side'].upper()} &nbsp;
              <span class="badge badge-green">EV {b['expected_value']:+.1%}</span>
              &nbsp; <span style="color:{COLORS['muted']};font-size:.85rem">{b['recommended_units']:.2f}u</span>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SLATE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "slate":
    back_btn()
    st.markdown('<div class="page-title">📋 Today\'s Slate</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Load live FanDuel lines, check the games you want, then run EV analysis</div>', unsafe_allow_html=True)

    if st.button("📥 Load Today's Games", type="primary"):
        with st.spinner("Fetching live FanDuel odds + AP rankings..."):
            try:
                games = get_live_games(ledger)
                st.session_state.all_games = games
                st.session_state.slate = None
                st.session_state.selected_ids = []
                st.toast(f"✅ Loaded {len(games)} games!", icon="🏀")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.all_games:
        all_games = st.session_state.all_games
        POWER = {"Big East","Big 12","SEC","ACC","Big Ten","Pac-12"}
        user_interests = ledger.get_interested_teams()

        def win_pct(r):
            try: w, l = r.split("-"); t = int(w)+int(l); return int(w)/t if t else 0
            except: return 0

        def intrigue(g):
            s = 0
            for s_ in [g.home_stats, g.away_stats]:
                if s_:
                    if s_.ranking: s += 10
                    if win_pct(s_.record) > 0.65: s += 5
                    if s_.conference in POWER: s += 3
                    s += 2
            
            # Boost if the user has shown interest previously
            s += (user_interests.get(g.home_team, 0) * 3)
            s += (user_interests.get(g.away_team, 0) * 3)
            
            return s

        sorted_games = sorted(all_games, key=intrigue, reverse=True)
        id_map = {g.game_id: g for g in all_games}
        ranked_n = sum(1 for g in all_games if
                       (g.home_stats and g.home_stats.ranking) or
                       (g.away_stats and g.away_stats.ranking))

        st.markdown("")
        st.markdown(
            f"""<div style="font-size:.82rem;color:{COLORS['muted']};margin-bottom:.8rem">
            {len(all_games)} games · {ranked_n} ranked matchups · 
            ⭐ = stats in DB · #N = AP rank · sorted by intrigue
            </div>""", unsafe_allow_html=True)

        if "game_checks" not in st.session_state:
            st.session_state.game_checks = {}
        if "slate_view_idx" not in st.session_state:
            st.session_state.slate_view_idx = 0

        selected_ids = [gid for gid, v in st.session_state.game_checks.items() if v]
        n_sel = len(selected_ids)

        # Top Control Row
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**Selected {n_sel} game{'s' if n_sel != 1 else ''}** for analysis.")
        with c2:
            if n_sel > 0:
                if st.button(f"▶ Analyze {n_sel} Game{'s' if n_sel != 1 else ''}", type="primary", use_container_width=True):
                    chosen = [id_map[gid] for gid in selected_ids if gid in id_map]
                    with st.spinner(f"🤖 Running EV analysis on {len(chosen)} game(s)..."):
                        try:
                            slate = run_async(analyze_full_slate(chosen, max_games=len(chosen)))
                            st.session_state.slate = slate
                            st.session_state.slate_error = None
                            st.session_state.page = "picks"
                            st.rerun()
                        except Exception as e:
                            st.session_state.slate_error = str(e)
                            st.error(str(e))

        st.markdown("---")

        idx = st.session_state.slate_view_idx
        if idx >= len(sorted_games):
            st.success(f"You've reviewed all {len(sorted_games)} games! Click Analyze above to proceed.")
            if st.button("↺ Start Over"):
                st.session_state.slate_view_idx = 0
                st.session_state.game_checks = {}
                st.rerun()
        else:
            g = sorted_games[idx]
            # 1. Base team data
            away_name  = g.away_team
            home_name  = g.home_team
            away_rank  = g.away_stats.ranking if g.away_stats else None
            home_rank  = g.home_stats.ranking if g.home_stats else None
            away_rec   = g.away_stats.record if g.away_stats else ""
            home_rec   = g.home_stats.record if g.home_stats else ""
            tip        = g.game_time.strftime("%I:%M %p ET")
            yyyymmdd   = g.game_time.strftime("%Y%m%d")

            # 2. Map local team names to ESPN IDs for logos and stat leaders
            away_espn_id = get_espn_team_id(away_name)
            home_espn_id = get_espn_team_id(home_name)
            
            # Fallback to local map if dynamic mapper failed
            if not away_espn_id:
                for n, eid in TEAM_ESPN_IDS.items():
                    if any(w in away_name for w in n.split()[:2]): away_espn_id = eid
            if not home_espn_id:
                for n, eid in TEAM_ESPN_IDS.items():
                    if any(w in home_name for w in n.split()[:2]): home_espn_id = eid

            # Venue is retrieved precisely from the schedule matching
            venue = fetch_game_venue(home_espn_id, away_name)

            # Live API spreads/totals are already stored in our DailyGame objects!
            spread = ""
            if g.home_odds and g.home_odds.line is not None:
                spread = f"{home_name.split()[0]} {g.home_odds.line:+g}"
            elif g.away_odds and g.away_odds.line is not None:
                spread = f"{away_name.split()[0]} {g.away_odds.line:+g}"
                
            ou = ""
            if g.total_over_odds and g.total_over_odds.line is not None:
                ou = f"O/U {g.total_over_odds.line:g}"

            away_logo = logo_url(away_espn_id) if away_espn_id else ""
            home_logo = logo_url(home_espn_id) if home_espn_id else ""

            @st.cache_data(ttl=3600)
            def _get_leaders(espn_id, tname):
                return fetch_team_stat_leaders(espn_id, tname) if espn_id else {}

            away_leaders = _get_leaders(away_espn_id, away_name)
            home_leaders = _get_leaders(home_espn_id, home_name)

            def _leader_pills(leaders: dict) -> str:
                pts = leaders.get('pts', {})
                reb = leaders.get('reb', {})
                ast = leaders.get('ast', {})
                return (
                    f'<span class="gc-pill"><b>PTS</b> {pts.get("name","—")} {pts.get("value","—")}</span>'
                    f'<span class="gc-pill"><b>REB</b> {reb.get("name","—")} {reb.get("value","—")}</span>'
                    f'<span class="gc-pill"><b>AST</b> {ast.get("name","—")} {ast.get("value","—")}</span>'
                ) if leaders else '<span class="gc-pill">Stats N/A</span>'

            # 3. Game preview bullet points
            blurb_html = generate_matchup_bullets(g, tip)

            # Flush-left HTML string to prevent Markdown code block bugs
            rank_badge_a = f'<div class="gc-rank">#{away_rank} AP</div>' if away_rank else ""
            rank_badge_h = f'<div class="gc-rank">#{home_rank} AP</div>' if home_rank else ""
            logo_tag_a   = f'<img src="{away_logo}" width="60" height="60" style="object-fit:contain" alt="{away_name}">' if away_logo else f'<div style="width:60px;height:60px;background:#1a2236;border-radius:8px;"></div>'
            logo_tag_h   = f'<img src="{home_logo}" width="60" height="60" style="object-fit:contain" alt="{home_name}">' if home_logo else f'<div style="width:60px;height:60px;background:#1a2236;border-radius:8px;"></div>'

            html_card = f"""
<div style="text-align:center;color:{COLORS['muted']};font-size:.85rem;margin-bottom:.5rem;">Game {idx+1} of {len(sorted_games)}</div>
<div class="game-card">
<div class="gc-team">
{logo_tag_a}
{rank_badge_a}
<div class="gc-tname">{away_name}</div>
<div class="gc-rec">{away_rec}</div>
<div class="gc-label">AWAY</div>
<div class="gc-leaders">{_leader_pills(away_leaders)}</div>
</div>
<div class="gc-vs">@</div>
<div class="gc-team">
{logo_tag_h}
{rank_badge_h}
<div class="gc-tname">{home_name}</div>
<div class="gc-rec">{home_rec}</div>
<div class="gc-label">HOME</div>
<div class="gc-leaders">{_leader_pills(home_leaders)}</div>
</div>
<div class="gc-mid">
<div style="font-size:.75rem;color:#fbbf24;font-weight:800">{tip}</div>
</div>
<div class="gc-blurb">💬 {blurb_html}</div>
</div>
"""
            st.markdown(html_card, unsafe_allow_html=True)

            cd1, cd2 = st.columns(2)
            if cd1.button(f"✖ Skip", key=f"skp_{g.game_id}", use_container_width=True):
                st.session_state.slate_view_idx += 1
                st.rerun()
                
            if cd2.button(f"🔥 Interested", key=f"int_{g.game_id}", type="primary", use_container_width=True):
                ledger.record_interest(g.home_team)
                ledger.record_interest(g.away_team)
                st.session_state.game_checks[g.game_id] = True
                st.session_state.slate_view_idx += 1
                st.rerun()

        selected_ids = [gid for gid, v in st.session_state.game_checks.items() if v]
        n_sel = len(selected_ids)

        st.markdown("")
    else:
        st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2.5rem">
          <div style="font-size:3rem">🏀</div>
          <div style="font-size:1.1rem;font-weight:600;margin:.5rem 0 .3rem">No games loaded yet</div>
          <div style="color:{COLORS['muted']}">Click <b>Load Today's Games</b> above to fetch live FanDuel lines</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PICKS & ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "picks":
    back_btn()
    st.markdown('<div class="page-title">📊 Picks & Analysis</div>', unsafe_allow_html=True)

    if st.session_state.slate_error:
        st.error(f"Analysis error: {st.session_state.slate_error}")
    elif st.session_state.slate is None:
        st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2.5rem">
          <div style="font-size:3rem">⚡</div>
          <div style="font-size:1.1rem;font-weight:600;margin:.5rem 0 .3rem">No analysis yet</div>
          <div style="color:{COLORS['muted']}">Go to <b>Today's Slate</b>, check your games, and click Analyze</div>
        </div>""", unsafe_allow_html=True)
        if st.button("← Go to Slate"):
            st.session_state.page = "slate"
            st.rerun()
    else:
        slate = st.session_state.slate
        recommended = [b for b in slate.bets if b.is_recommended]

        # ─ Summary bar ────────────────────────────────────────────────────────
        c1, c2, c3 = st.columns(3)
        c1.metric("Games Analyzed", slate.games_analyzed)
        c2.metric("+EV Bets Found", len(recommended))
        c3.metric("Units at Risk", f"{slate.total_units_at_risk:.2f}u")
        st.markdown("")

        if not recommended:
            st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2rem">
              <div style="font-size:2.5rem">🙌</div>
              <div style="font-weight:700;margin:.4rem 0 .2rem">No edges today</div>
              <div style="color:{COLORS['muted']}">No bets cleared the +3.5% EV threshold. Sit on your hands.</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="page-sub">{len(recommended)} bet(s) passed +EV threshold '  # noqa
                '&nbsp;·&nbsp; <b style="color:#22c55e">📌 Place Bet</b> to add to pending '  # noqa
                '&nbsp;·&nbsp; <b style="color:#ef4444">✖ Skip</b> to dismiss</div>',
                unsafe_allow_html=True,
            )

            # Track which bets have been placed / skipped in this session
            if "placed_bets" not in st.session_state:
                st.session_state.placed_bets = set()
            if "skipped_bets" not in st.session_state:
                st.session_state.skipped_bets = set()

            for rec in recommended:
                ev = rec.ev_analysis.expected_value
                line_str = f" {rec.line:+.1f}" if rec.line else ""
                tip = rec.game_time.strftime("%I:%M %p ET") if rec.game_time else ""
                bet_key = f"{rec.game_id}_{rec.bet_type.value}_{rec.side.value}"

                already_placed = bet_key in st.session_state.placed_bets
                already_skipped = bet_key in st.session_state.skipped_bets

                # ─ Card: all pure Streamlit, no HTML wrapper above the buttons ───
                left, right = st.columns([5, 2])
                with left:
                    game_line = (
                        f"**{rec.away_team}** @ **{rec.home_team}**"
                        f"\u2003— `{rec.bet_type.value.upper()} {rec.side.value.upper()}{line_str}`"
                        f" {'%+d' % rec.american_odds}"
                    )
                    st.markdown(game_line)
                    st.caption(
                        f"{tip} · Kelly: **{rec.recommended_units:.2f}u** · {ev_badge(ev)}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"*{rec.summary}*")

                with right:
                    if already_placed:
                        st.success("Placed ✓")
                    elif already_skipped:
                        st.warning("Skipped")
                    else:
                        p_col, s_col = st.columns(2)
                        with p_col.popover("📌 Place", use_container_width=True):
                            st.markdown("**Confirm Unit Sizing:**")
                            actual_units = st.number_input(
                                "Units",
                                value=float(round(rec.recommended_units, 2)),
                                step=0.1,
                                format="%.2f",
                                key=f"units_{bet_key}",
                                label_visibility="collapsed"
                            )
                            if st.button("Confirm Bet", type="primary", key=f"confirm_{bet_key}", use_container_width=True):
                                rec.recommended_units = actual_units
                                bid = ledger.save_recommendation(rec)
                                ledger.approve_bet(bid)
                                st.session_state.placed_bets.add(bet_key)
                                st.rerun()

                        if s_col.button(
                            "✖ Skip",
                            key=f"skip_{bet_key}",
                            use_container_width=True,
                        ):
                            st.session_state.skipped_bets.add(bet_key)
                            st.rerun()

                # ─ Reasoning expander — color coded by confidence ─
                ev   = rec.ev_analysis.expected_value
                conf = rec.ev_analysis.confidence
                if ev >= 0.05 and conf >= 0.75:
                    reason_bg  = "rgba(34,197,94,.08)"
                    reason_bdr = "rgba(34,197,94,.35)"
                    reason_ico = "🔥 HIGH CONFIDENCE"
                    reason_col = "#22c55e"
                elif ev >= 0.035 or conf >= 0.60:
                    reason_bg  = "rgba(251,191,36,.08)"
                    reason_bdr = "rgba(251,191,36,.35)"
                    reason_ico = "⚡ MODERATE"
                    reason_col = "#fbbf24"
                else:
                    reason_bg  = "rgba(239,68,68,.07)"
                    reason_bdr = "rgba(239,68,68,.3)"
                    reason_ico = "⚠️ LOW CONFIDENCE"
                    reason_col = "#ef4444"

                st.markdown(
                    f'<div style="background:{reason_bg};border:1px solid {reason_bdr};'
                    f'border-radius:10px;padding:.6rem .9rem;margin:.4rem 0 .2rem;'
                    f'font-size:.7rem;font-weight:700;color:{reason_col};letter-spacing:.08em">'
                    f'{reason_ico} · EV {ev:+.1%} · Conf {conf:.0%}</div>',
                    unsafe_allow_html=True,
                )
                with st.expander("🧠 Reasoning", expanded=False):
                    st.markdown(
                        f'<div style="background:{reason_bg};border-radius:8px;padding:1rem">',
                        unsafe_allow_html=True,
                    )
                    for i, step in enumerate(rec.ev_analysis.reasoning_steps, 1):
                        st.markdown(f"**{i}.** {step}")
                    st.markdown("</div>", unsafe_allow_html=True)
                    cc = st.columns(4)
                    cc[0].metric("Win Prob", f"{rec.ev_analysis.projected_win_probability:.1%}")
                    cc[1].metric("Implied",  f"{rec.ev_analysis.implied_probability:.1%}")
                    cc[2].metric("EV",       f"{rec.ev_analysis.expected_value:+.1%}")
                    cc[3].metric("Conf.",    f"{rec.ev_analysis.confidence:.0%}")

                st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PENDING BETS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "pending":
    back_btn()
    st.markdown('<div class="page-title">⏳ Pending Bets</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Manage and settle your active positions</div>', unsafe_allow_html=True)

    pending = list(ledger.db["bets"].rows_where("status IN ('pending','approved')", []))
    pending_parlays = ledger.get_pending_parlays()

    # ── Danger zone: clear all ────────────────────────────────────────────────
    if pending or pending_parlays:
        with st.expander("⚠️ Danger zone"):
            st.warning("This will permanently delete ALL pending and approved bets and parlays.")
            if st.button("🗑 Clear All Pending", type="primary"):
                ledger.db.execute("DELETE FROM bets WHERE status IN ('pending','approved')")
                ledger.db.execute("DELETE FROM parlays WHERE status = 'pending'")
                ledger.db.conn.commit()
                st.success("All pending cleared.")
                st.rerun()

    if not pending and not pending_parlays:
        st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2.5rem">
          <div style="font-size:3rem">✅</div>
          <div style="font-weight:700;margin:.4rem 0 .2rem">All clear</div>
          <div style="color:{COLORS['muted']}">No pending bets or parlays. Head to <b>Today's Slate</b> to generate picks.</div>
        </div>""", unsafe_allow_html=True)
    else:
        if pending:
            st.markdown(f'<div class="indie-section-hdr">Single Bets</div>', unsafe_allow_html=True)
            for bet in pending:
                icon  = "✅" if bet["status"] == "approved" else "🕐"
                with st.expander(
                    f"{icon} {bet['away_team']} @ {bet['home_team']}  ·  "
                    f"{bet['bet_type'].upper()} {bet['side'].upper()}  "
                    f"({'%+d' % bet['american_odds']})  ·  EV {bet['expected_value']:+.1%}  ·  {bet['recommended_units']:.2f}u"
                ):
                    st.markdown(f"**ID:** `{bet['id'][:8]}` &nbsp;&nbsp; **Status:** `{bet['status'].upper()}`")
                    st.markdown(f"**Summary:** {bet['summary']}")

                    action_cols = st.columns([1, 1, 1, 3])
                    if bet["status"] == "pending":
                        if action_cols[0].button("✅ Approve", key=f"pa_{bet['id'][:8]}"):
                            ledger.approve_bet(bet["id"])
                            st.success("Approved!")
                            st.rerun()
                    if action_cols[1].button("🗑 Remove", key=f"del_{bet['id'][:8]}",
                                              help="Delete this bet without settling"):
                        ledger.db.execute("DELETE FROM bets WHERE id = ?", [bet["id"]])
                        ledger.db.conn.commit()
                        st.success("Bet removed.")
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Settle this bet:**")
                    sc1, sc2, sc3 = st.columns([2, 2, 1])
                    result = sc1.selectbox("Result", ["win","loss","push"], key=f"res_{bet['id'][:8]}")
                    pl     = sc2.number_input("P/L (units)", value=float(bet["recommended_units"]),
                                               step=0.01, key=f"pl_{bet['id'][:8]}")
                if sc3.button("Settle", key=f"st_{bet['id'][:8]}"):
                    ledger.settle_bet(bet["id"], result, pl if result != "loss" else -abs(pl))
                    st.success(f"Settled as {result.upper()}!")
                    st.rerun()

        if pending_parlays:
            st.markdown(f'<div class="indie-section-hdr" style="margin-top:2rem">Parlays</div>', unsafe_allow_html=True)
            for p in pending_parlays:
                leg_ids = json.loads(p["leg_ids"])
                with st.expander(
                    f"🔗 {len(leg_ids)}-Leg Parlay  ·  Odds ({p['american_odds']:+d})  ·  {p['recommended_units']:.2f}u"
                ):
                    st.markdown(f"**ID:** `{p['id'][:8]}` &nbsp;&nbsp; **Status:** `{p['status'].upper()}`")
                    st.markdown("**Legs:**")
                    for lid in leg_ids:
                        leg_row = list(ledger.db["bets"].rows_where("id = ?", [lid]))
                        if leg_row:
                            leg = leg_row[0]
                            st.markdown(f"- {leg['away_team']} @ {leg['home_team']} | {leg['bet_type'].upper()} {leg['side'].upper()}")
                            
                    action_cols = st.columns([1, 1, 1, 3])
                    if action_cols[0].button("🗑 Remove", key=f"pdel_{p['id'][:8]}", help="Delete this parlay"):
                        ledger.db.execute("DELETE FROM parlays WHERE id = ?", [p["id"]])
                        ledger.db.conn.commit()
                        st.success("Parlay removed.")
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Settle this parlay:**")
                    psc1, psc2, psc3 = st.columns([2, 2, 1])
                    result = psc1.selectbox("Result", ["win","loss","push"], key=f"pres_{p['id'][:8]}")
                    pl     = psc2.number_input("P/L (units)", value=float(p["recommended_units"]),
                                               step=0.01, key=f"ppl_{p['id'][:8]}")
                    if psc3.button("Settle", key=f"pst_{p['id'][:8]}"):
                        ledger.settle_parlay(p["id"], result, pl if result != "loss" else -abs(pl))
                        st.success(f"Settled as {result.upper()}!")
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "history":
    back_btn()
    st.markdown('<div class="page-title">📈 Performance</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Your betting record and bankroll history</div>', unsafe_allow_html=True)

    bankroll = ledger.get_bankroll()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Balance", f"{bankroll['balance_units']:.1f}u")
    c2.metric("Unit Size", f"${bankroll['unit_dollar_value']:.2f}")
    c3.metric("Record", f"{wins}W – {losses}L")
    c4.metric("All-time P/L", f"{total_pl:+.2f}u",
              delta_color="normal" if total_pl >= 0 else "inverse")

    with st.expander("⚙️ Bankroll Settings"):
        with st.form("bankroll_form"):
            new_bal = st.number_input("Starting/Current Balance (Units)", value=float(bankroll['balance_units']), step=1.0)
            new_unit = st.number_input("Dollar Value per Unit ($)", value=float(bankroll['unit_dollar_value']), step=5.0)
            if st.form_submit_button("Update Bankroll"):
                ledger.db.execute("UPDATE bankroll SET balance_units = ?, unit_dollar_value = ? WHERE id = 1", [new_bal, new_unit])
                ledger.db.conn.commit()
                st.success("Bankroll updated!")
                st.rerun()

    st.markdown("")
    
    settled_all = settled + settled_parlays
    if settled_all:
        st.markdown('<div class="page-title" style="font-size:1.1rem">📊 Bankroll Trend</div>', unsafe_allow_html=True)
        # Sort chronologically by created date
        sorted_settled = sorted(settled_all, key=lambda x: x.get("created_at", ""))
        cum_pl = 0.0
        history_data = [{"Bet": 0, "Cumulative P/L (Units)": 0.0}]
        
        for i, b in enumerate(sorted_settled, 1):
            if b.get("profit_loss") is not None:
                cum_pl += b["profit_loss"]
            history_data.append({"Bet": i, "Cumulative P/L (Units)": cum_pl})
            
        st.line_chart(history_data, x="Bet", y="Cumulative P/L (Units)", use_container_width=True, color="#22c55e")
        st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="page-title" style="font-size:1.1rem">📜 Settled Bets</div>', unsafe_allow_html=True)

    if not settled_all:
        st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2rem">
          <div style="color:{COLORS['muted']}">No settled bets yet. Approve some picks and settle them after games.</div>
        </div>""", unsafe_allow_html=True)
    else:
        rows = []
        for b in settled:
            rows.append({
                "Game": f"{b['away_team']} @ {b['home_team']}",
                "Market": f"{b['bet_type'].upper()} {b['side'].upper()}",
                "Odds": f"{'%+d' % b['american_odds']}",
                "EV": f"{b['expected_value']:+.1%}",
                "Units": f"{b['recommended_units']:.2f}u",
                "Result": (b["result"] or "").upper(),
                "P/L": f"{b['profit_loss']:+.2f}u" if b["profit_loss"] is not None else "",
                "Time": b.get("created_at", "")
            })
        for p in settled_parlays:
            rows.append({
                "Game": f"Parlay ({len(json.loads(p['leg_ids']))} legs)",
                "Market": "PARLAY",
                "Odds": f"{'%+d' % p['american_odds']}",
                "EV": "-",
                "Units": f"{p['recommended_units']:.2f}u",
                "Result": (p["result"] or "").upper(),
                "P/L": f"{p['profit_loss']:+.2f}u" if p["profit_loss"] is not None else "",
                "Time": p.get("created_at", "")
            })
        
        rows.sort(key=lambda x: x.get("Time", ""), reverse=True)
        for r in rows:
            if "Time" in r:
                del r["Time"]
        
        st.dataframe(rows, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PARLAYS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "parlays":
    back_btn()
    st.markdown('<div class="page-title">🔗 Parlay Builder</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Combine approved bets for bigger payouts</div>', unsafe_allow_html=True)

    approved = ledger.get_approved_bets()
    if not approved:
        st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2.5rem">
          <div style="font-size:3rem">🔗</div>
          <div style="font-size:1.1rem;font-weight:600;margin:.5rem 0 .3rem">No approved bets available</div>
          <div style="color:{COLORS['muted']}">Approve some picks from the Pending Bets tab first</div>
        </div>""", unsafe_allow_html=True)
    else:
        if "parlay_selections" not in st.session_state:
            st.session_state.parlay_selections = {}

        st.markdown(f'<div class="indie-section-hdr" style="margin-top:1rem">Select Legs</div>', unsafe_allow_html=True)
        
        selected_legs = []
        for b in approved:
            checked = st.session_state.parlay_selections.get(b["id"], False)
            title = f"{b['away_team']} @ {b['home_team']} | {b['bet_type'].upper()} {b['side'].upper()} ({b['american_odds']:+d})"
            new_val = st.checkbox(title, value=checked, key=f"pchk_{b['id']}")
            if new_val != checked:
                st.session_state.parlay_selections[b["id"]] = new_val
                st.rerun()
            if new_val:
                selected_legs.append(b)

        if len(selected_legs) > 1:
            st.markdown("---")
            st.markdown(f'<div class="indie-section-hdr">Ticket ({len(selected_legs)} legs)</div>', unsafe_allow_html=True)
            
            # Mathematical compound odds
            compound_decimal = 1.0
            for leg in selected_legs:
                odds = leg["american_odds"]
                if odds > 0:
                    dec = (odds / 100.0) + 1.0
                else:
                    dec = (100.0 / abs(odds)) + 1.0
                compound_decimal *= dec
                
            if compound_decimal >= 2.0:
                parlay_american = int((compound_decimal - 1.0) * 100)
            else:
                parlay_american = int(-100.0 / (compound_decimal - 1.0))
                
            implied_prob = 1.0 / compound_decimal
            
            st.markdown(f"""<div class="glass-card" style="padding:1.5rem">
              <div style="display:flex;justify-content:space-between">
                <span><b>Combined Odds:</b> <span class="badge badge-green">{parlay_american:+d}</span></span>
                <span><b>Implied Prob:</b> {implied_prob:.1%}</span>
              </div>
            </div>""", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            units = st.number_input("Parlay Units", min_value=0.1, value=1.0, step=0.1)
            
            if st.button("🔒 Lock in Parlay", type="primary", use_container_width=True):
                leg_ids = [leg["id"] for leg in selected_legs]
                ledger.save_parlay(leg_ids, parlay_american, implied_prob, units)
                st.session_state.parlay_selections = {}
                st.success("Parlay locked in!")
                st.rerun()
        elif len(selected_legs) == 1:
            st.info("Select at least 2 legs to build a parlay.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: GAME SEARCH
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "search":
    back_btn()
    st.markdown('<div class="page-title">🔍 Game Search</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Type a team, conference, or keyword — get live FanDuel odds instantly</div>', unsafe_allow_html=True)

    for msg in st.session_state.search_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    if not st.session_state.search_messages:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="page-title" style="font-size:1.1rem">🔥 Hot Games Today</div>', unsafe_allow_html=True)
        
        if not st.session_state.all_games:
            st.info("Live odds and rankings aren't loaded into memory yet.")
            if st.button("📥 Load Live Games", type="primary"):
                with st.spinner("Fetching live FanDuel odds + AP rankings..."):
                    try:
                        st.session_state.all_games = get_live_games(ledger)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            all_games = st.session_state.all_games
            POWER = {"Big East","Big 12","SEC","ACC","Big Ten","Pac-12"}
            user_interests = ledger.get_interested_teams()
            
            def win_pct(r):
                try: w, l = r.split("-"); t = int(w)+int(l); return int(w)/t if t else 0
                except: return 0
                
            def intrigue(g):
                s = 0
                for s_ in [g.home_stats, g.away_stats]:
                    if s_:
                        if s_.ranking: s += 10
                        if win_pct(s_.record) > 0.65: s += 5
                        if s_.conference in POWER: s += 3
                        s += 2
                        
                # Boost if the user has shown interest previously
                s += (user_interests.get(g.home_team, 0) * 3)
                s += (user_interests.get(g.away_team, 0) * 3)
                
                return s
                
            hot_games = sorted(all_games, key=intrigue, reverse=True)[:3]
            
            h1, h2, h3 = st.columns(3)
            for col, g in zip([h1, h2, h3], hot_games):
                with col:
                    h_rank = f"#{g.home_stats.ranking} " if g.home_stats and g.home_stats.ranking else ""
                    a_rank = f"#{g.away_stats.ranking} " if g.away_stats and g.away_stats.ranking else ""
                    tip = g.game_time.strftime("%I:%M %p ET")
                    spread = f"{g.home_team.split()[0]} {g.home_odds.line:+.1f}" if g.home_odds and g.home_odds.line else ""
                    
                    st.markdown(f"""
                    <div style="background:#111827;border:1px solid #1e2d45;border-radius:12px;padding:1rem;margin-bottom:.5rem;">
                      <div style="font-size:.75rem;color:#fbbf24;font-weight:700;margin-bottom:.4rem">{tip}</div>
                      <div style="font-weight:700;line-height:1.3;font-size:.95rem">
                        <span style="color:#94a3b8;font-size:.8rem">{a_rank}</span>{g.away_team}<br>
                        <span style="color:#64748b;font-size:.8rem">@</span><br>
                        <span style="color:#94a3b8;font-size:.8rem">{h_rank}</span>{g.home_team}
                      </div>
                      <div style="font-size:.8rem;color:{COLORS['green']};margin-top:.6rem;font-weight:800">
                        {spread}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Analyze", key=f"hot_{g.game_id}", use_container_width=True):
                        with st.spinner("🤖 Running EV analysis..."):
                            try:
                                slate = run_async(analyze_full_slate([g], max_games=1))
                                st.session_state.slate = slate
                                st.session_state.slate_error = None
                                st.session_state.page = "picks"
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

    query = st.chat_input("Search e.g. 'Kansas', 'Big East', 'Auburn'...")

    if query:
        st.session_state.search_messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("Searching..."):
                if st.session_state.all_games is None:
                    try:
                        st.session_state.all_games = get_live_games(ledger)
                    except Exception as e:
                        msg = f"⚠️ Couldn't load games: {e}"
                        st.error(msg)
                        st.session_state.search_messages.append({"role":"assistant","content":msg})
                        st.stop()

                q = query.lower().strip()
                matches = [g for g in st.session_state.all_games if q in " ".join(filter(None, [
                    g.home_team, g.away_team,
                    g.home_stats.conference if g.home_stats else "",
                    g.away_stats.conference if g.away_stats else "",
                ])).lower()]

                if not matches:
                    reply = f'❌ No games matching **"{query}"** on today\'s slate.'
                    st.markdown(reply)
                    st.session_state.search_messages.append({"role":"assistant","content":reply})
                else:
                    st.markdown(f"Found **{len(matches)} game(s)** matching **\"{query}\"**:")
                    lines = []
                    for g in matches:
                        tip   = g.game_time.strftime("%I:%M %p ET")
                        sp    = (f"Spread: {g.home_team} {g.home_odds.line:+.1f} "
                                 f"({'%+d' % g.home_odds.american_odds}) / "
                                 f"{g.away_team} {g.away_odds.line:+.1f} "
                                 f"({'%+d' % g.away_odds.american_odds})"
                                 if g.home_odds and g.away_odds else "No spread")
                        tot   = (f"O/U {g.total_over_odds.line} "
                                 f"(O {'%+d' % g.total_over_odds.american_odds} / "
                                 f"U {'%+d' % g.total_under_odds.american_odds})"
                                 if g.total_over_odds and g.total_under_odds else "No total")
                        ml    = (f"ML: {g.home_team} {'%+d' % g.home_ml.american_odds} / "
                                 f"{g.away_team} {'%+d' % g.away_ml.american_odds}"
                                 if g.home_ml and g.away_ml else "")
                        conf  = f" · {g.home_stats.conference}" if (g.home_stats and g.home_stats.conference) else ""
                        blurb = generate_matchup_bullets(g, tip)
                        card = f"""<div class="glass-card accent" style="margin:.5rem 0;margin-bottom:0">
<div style="font-weight:800;font-size:1rem">{g.away_team} <span style="color:{COLORS['muted']}">@</span> {g.home_team}
<span style="font-size:.75rem;color:{COLORS['muted']};font-weight:400;margin-left:8px">{tip}{conf}</span></div>
<div style="font-size:.85rem;color:{COLORS['text2']};margin-top:.4rem">📊 {sp}</div>
<div style="font-size:.85rem;color:{COLORS['text2']}">🎯 {tot}</div>
{"<div style='font-size:.85rem;color:"+COLORS['text2']+"'>💰 "+ml+"</div>" if ml else ""}
<div style="margin-top:.6rem;padding-top:.4rem;border-top:1px dashed {COLORS['border']};font-size:.82rem;line-height:1.5;color:{COLORS['text']}">
{blurb}
</div>
</div>"""
                        st.markdown(card, unsafe_allow_html=True)
                        if st.button(f"🔍 Analyze {g.away_team} @ {g.home_team}", key=f"analyze_{g.game_id}", use_container_width=True):
                            with st.spinner("🤖 Running EV analysis on this game..."):
                                try:
                                    # run_async is defined globally in app.py
                                    slate = run_async(analyze_full_slate([g], max_games=1))
                                    st.session_state.slate = slate
                                    st.session_state.slate_error = None
                                    st.session_state.page = "picks"
                                    st.rerun()
                                except Exception as e:
                                    st.error(str(e))
                                    
                        lines.append(f"• {g.away_team} @ {g.home_team} — {sp} | {tot}")
                    st.session_state.search_messages.append({"role":"assistant","content":"\n".join(lines)})

    if st.session_state.search_messages:
        if st.button("🗑 Clear Search History"):
            st.session_state.search_messages = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TEAMS EXPLORER
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "teams":

    # ─ Inline renderers (no nested dialogs) ──────────────────────────────────────
    def _render_player(container, player_data: dict):
        """Render player bio + scouting notes into a given container (uses roster dict directly)."""
        with container:
            info = fetch_player_stats(player_data)
            if not info or not info.get("name"):
                st.caption("Player data unavailable.")
                return
            c1, c2 = st.columns([1, 3])
            with c1:
                if info.get("headshot"):
                    st.image(info["headshot"], width=100)
            with c2:
                st.markdown(f"**{info['name']}**")
                pos  = info.get("position", "")
                ht   = info.get("height", "")
                wt   = info.get("weight", "")
                city = info.get("birthPlace", "")
                yr   = info.get("year", "")
                st.caption(f"{pos}  ·  {ht}, {wt} lbs  ·  {yr}  ·  {city}")
                roster_stats = info.get("stats", {})
                if roster_stats:
                    stat_cols = list(roster_stats.items())[:8]
                    cols = st.columns(len(stat_cols))
                    for col, (k, v) in zip(cols, stat_cols):
                        col.metric(k, v)
            traits = {
                "PG": "🎯 Floor general — playmaking, A/TO ratio, pick-and-roll reads.",
                "SG": "🎯 Shooting guard — off-ball movement, catch-and-shoot, two-way.",
                "SF": "🎯 Small forward — wing defense, transition scoring, rebounding.",
                "PF": "🎯 Power forward — paint presence, screen quality, face-up game.",
                "C":  "🎯 Center — rim protection, offensive rebounding, P&R defense.",
            }
            pos_key = pos.upper()[:2]
            note = traits.get(pos_key, "🎯 Versatile player — evaluate holistically.")
            st.info(note)

    def _render_boxscore(container, event_id: str, game_name: str):
        """Render a box score table into a given container."""
        with container:
            with st.spinner("Loading box score..."):
                bs = fetch_boxscore(event_id)
            if not bs or not bs.get("teams"):
                st.caption("Box score not available.")
                return
            if bs.get("result"):
                st.markdown(f"**Final:** {bs['result']}")
            for team in bs["teams"]:
                st.markdown(f"**{team['team']}**")
                players = team.get("players", [])
                if not players:
                    st.caption("No player data.")
                    continue
                # labels sit on each player row (same for all players in team)
                labels = players[0].get("labels", [])
                rows = []
                for p in players:
                    row = {"Player": p["name"], "Pos": p.get("position", "")}
                    for lbl, val in zip(labels, p.get("stats", [])):
                        row[lbl] = val
                    rows.append(row)
                st.dataframe(rows, use_container_width=True, hide_index=True)

    @st.dialog("🏀 Team Details", width="large")
    def show_team(team_name: str, espn_id: int, db_ranking: Optional[int]):
        with st.spinner(f"Loading {team_name}..."):
            summary  = fetch_team_summary(espn_id)
            roster   = fetch_team_roster(espn_id)
            schedule = fetch_team_schedule(espn_id)
        best_wins, worst_losses = fetch_best_worst(schedule, espn_id)

        # ─ Header ────────────────────────────────────────────────────
        h1, h2 = st.columns([1, 4])
        with h1:
            st.image(logo_url(espn_id), width=90)
        with h2:
            # Prefer live ESPN rank over DB ranking
            espn_rank = summary.get("rank")  # directly from ESPN API
            effective_rank = espn_rank or db_ranking
            rank_str = f' · <span style="background:#f97316;color:white;border-radius:20px;padding:2px 9px;font-size:.8rem;font-weight:900">#{effective_rank} AP</span>' if effective_rank else ""
            st.markdown(
                f"## {summary.get('name', team_name)}{rank_str}",
                unsafe_allow_html=True,
            )
            rec = summary.get("record", "")
            home_rec = summary.get("home_record", "")
            road_rec = summary.get("road_record", "")
            standing = summary.get("standing", "")

            meta_parts = []
            if rec:
                meta_parts.append(f"`{rec}` overall")
            if home_rec:
                meta_parts.append(f"`{home_rec}` home")
            if road_rec:
                meta_parts.append(f"`{road_rec}` road")
            st.markdown("  ·  ".join(meta_parts))
            if standing:
                st.markdown(f"**🏆 Conference Standing:** {standing}")

            # ─ Best wins (green) + worst losses (red) ──────────────────────
            chips = []
            for g in best_wins:
                chips.append(
                    f'<span style="background:rgba(34,197,94,.18);color:#22c55e;'
                    f'border:1px solid rgba(34,197,94,.4);border-radius:20px;'
                    f'padding:2px 10px;font-size:.75rem;font-weight:600;white-space:nowrap">'
                    f"✅ W {g['our_score']}–{g['opp_score']} {g.get('opp_name','').split()[-1]}"
                    f"</span>"
                )
            for g in worst_losses:
                chips.append(
                    f'<span style="background:rgba(239,68,68,.15);color:#ef4444;'
                    f'border:1px solid rgba(239,68,68,.35);border-radius:20px;'
                    f'padding:2px 10px;font-size:.75rem;font-weight:600;white-space:nowrap">'
                    f"❌ L {g['our_score']}–{g['opp_score']} {g.get('opp_name','').split()[-1]}"
                    f"</span>"
                )
            if chips:
                st.markdown(
                    '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:.4rem">'
                    + "".join(chips) + "</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        t_roster, t_sched, t_facts = st.tabs(["Roster", "Schedule", "Facts"])

        # ─ Roster tab ────────────────────────────────────────────────
        with t_roster:
            if not roster:
                st.info("Roster not available.")
            else:
                cols = st.columns(3)
                for i, p in enumerate(roster):
                    with cols[i % 3]:
                        headshot = p.get("headshot", "")
                        pos_tag  = p.get("position", "")
                        year_tag = p.get("year", "")
                        jersey   = p.get("jersey", "")
                        ht_raw   = p.get("height", "")
                        ht_tag   = inches_to_ft(ht_raw) if ht_raw else ""
                        if ht_tag:
                            ht_tag = f" · {ht_tag}"
                            
                        card_html = f"""
<div style="background:#1a2236;border:1px solid #1e2d45;border-radius:12px;
            padding:.8rem;margin-bottom:.4rem;text-align:center">
{f'<img src="{headshot}" style="width:56px;height:56px;border-radius:50%;object-fit:cover;margin-bottom:.3rem">' if headshot else '<div style="width:56px;height:56px;border-radius:50%;background:#2d4a6e;margin:0 auto .3rem;line-height:56px;font-size:1.1rem">👤</div>'}
<div style="font-weight:700;font-size:.85rem">{p['name']}</div>
<div style="font-size:.72rem;color:#6b7280">#{jersey} · {pos_tag}{ht_tag} · {year_tag}</div>
</div>"""
                        st.markdown(card_html, unsafe_allow_html=True)
                        with st.expander("Stats & Scouting"):
                            _render_player(st.container(), p)

        # ─ Schedule tab ───────────────────────────────────────────────
        with t_sched:
            if not schedule:
                st.info("Schedule not available.")
            else:
                # Most recent first
                sorted_sched = sorted(
                    schedule, key=lambda g: g.get("date", ""), reverse=True
                )
                for game in sorted_sched:
                    date_str  = game["date"][:10] if game["date"] else ""
                    completed = game.get("completed", False)
                    hs  = game.get("home_score")
                    aws = game.get("away_score")
                    status = game.get("status", "")

                    won = None
                    if completed and hs is not None and aws is not None:
                        try:
                            team_is_home = game.get("team_is_home", True)
                            our = int(hs) if team_is_home else int(aws)
                            opp = int(aws) if team_is_home else int(hs)
                            won = our > opp
                            score_str = f"{hs}–{aws}"
                        except (ValueError, TypeError):
                            score_str = f"{hs}–{aws}"
                    elif not completed:
                        score_str = status
                    else:
                        score_str = status

                    if won is True:
                        bg, border, pill = "rgba(34,197,94,.12)", "rgba(34,197,94,.4)", "✅ W"
                    elif won is False:
                        bg, border, pill = "rgba(239,68,68,.10)", "rgba(239,68,68,.35)", "❌ L"
                    else:
                        bg, border, pill = "transparent", "#1e2d45", "🕐"

                    if completed:
                        with st.expander(
                            f"{pill}  {game['name']}  ·  {score_str}  ·  {date_str}"
                        ):
                            _render_boxscore(
                                st.container(), str(game["event_id"]), game["name"]
                            )
                    else:
                        st.markdown(
                            f'<div style="background:{bg};border:1px solid {border};'
                            f'border-radius:8px;padding:.4rem .8rem;margin-bottom:.3rem;'
                            f'font-size:.85rem;display:flex;gap:.6rem;align-items:center">'
                            f'<span style="color:#6b7280;min-width:82px">{date_str}</span>'
                            f'<span style="flex:1;font-weight:600">{game["name"]}</span>'
                            f'<span style="color:#94a3b8">{score_str}</span></div>',
                            unsafe_allow_html=True,
                        )

        # ─ Facts tab ──────────────────────────────────────────────────
        with t_facts:
            db_stats = None
            for s in ledger.get_all_team_stats():
                if (s.get("team_name", "").lower() in team_name.lower()
                        or team_name.lower() in s.get("team_name", "").lower()):
                    db_stats = s
                    break

            loc  = summary.get("location", "")
            nick = summary.get("nickname", "")
            rec  = summary.get("record", "—")
            st.markdown(f"**{summary.get('name', team_name)}**  ·  {loc}  ·  {nick}")
            st.markdown(f"**Record:** `{rec}`")

            if not db_stats:
                st.info("Detailed scouting data not in our database for this team.")
            else:
                oe   = float(db_stats.get("offensive_efficiency", 0) or 0)
                de   = float(db_stats.get("defensive_efficiency",  0) or 0)
                pace = float(db_stats.get("pace",                  0) or 0)
                tpr  = float(db_stats.get("three_point_rate",      0) or 0)
                ats  = db_stats.get("ats_record", "")
                net  = oe - de

                st.markdown("---")
                st.markdown("**📊 Performance Metrics**")
                fm1, fm2, fm3, fm4 = st.columns(4)
                fm1.metric("Off. Efficiency", f"{oe:.1f}")
                fm2.metric("Def. Efficiency", f"{de:.1f}")
                fm3.metric("Net Margin",      f"{net:+.1f}")
                fm4.metric("3PT Rate",        f"{tpr:.1%}")
                if ats:
                    st.markdown(f"**ATS Record:** {ats}  ·  **Pace:** {pace:.1f} poss/game")

                # ── Scouting report ──────────────────────────────────────
                st.markdown("---")
                st.markdown("**🔍 Scouting Report**")

                strengths: list[str] = []
                weaknesses: list[str] = []

                # Offense — tightened for elite pool (avg among ranked teams ~113)
                if oe >= 117:
                    strengths.append(f"**Elite offense** (OE {oe:.1f}) — one of the country's most efficient attacks; scores against any scheme.")
                elif oe >= 110:
                    strengths.append(f"**Efficient offense** (OE {oe:.1f}) — generates quality looks and converts at a high rate.")
                else:
                    weaknesses.append(f"**Below-average offense** (OE {oe:.1f}) for a ranked program — opposing defenses can neutralise them on tough nights.")

                # Defense — tightened (avg among ranked teams ~99)
                if de <= 94:
                    strengths.append(f"**Suffocating defense** (DE {de:.1f}) — elite unit; opponents rarely score efficiently. Carries close games.")
                elif de <= 99:
                    strengths.append(f"**Solid defense** (DE {de:.1f}) — limits easy baskets and second chances; above national average.")
                elif de <= 104:
                    weaknesses.append(f"**Porous defense** (DE {de:.1f}) — gives up efficient looks; opponents cash in on mistakes.")
                else:
                    weaknesses.append(f"**Defensive liability** (DE {de:.1f}) — opponents score at will; must win shootouts to cover spreads.")

                # Pace
                if pace >= 73:
                    strengths.append(f"**Up-tempo** ({pace:.1f} poss/game) — forces the pace, exploits slow rotations, and racks up possessions.")
                elif pace <= 64:
                    weaknesses.append(f"**Slow grind** ({pace:.1f} poss/game) — methodical halfcourt team; totals consistently track under, tough to watch late.")
                else:
                    strengths.append(f"**Balanced tempo** ({pace:.1f} poss/game) — flexible; adapts to opponent's preferred pace.")

                # Three-point rate
                if tpr >= 0.40:
                    strengths.append(f"**Arc-heavy offense** ({tpr:.0%} 3PT rate) — nearly unguardable on a hot night; but high variance when cold.")
                elif tpr >= 0.34:
                    strengths.append(f"**Perimeter depth** ({tpr:.0%} 3PT rate) — spreads the floor and creates driving lanes.")
                else:
                    weaknesses.append(f"**Limited perimeter game** ({tpr:.0%} 3PT rate) — defenses pack the paint; relies on interior scoring and FTs.")

                # Net efficiency → relative strength/weakness
                if net >= 15:
                    strengths.append(f"**Dominant net margin (+{net:.1f})** — elite two-way team; rarely squanders double-digit leads.")
                elif net >= 8:
                    strengths.append(f"**Positive net margin (+{net:.1f})** — consistently out-executes opponents across 40 minutes.")
                elif net >= 2:
                    weaknesses.append(f"**Thin margin (+{net:.1f})** — close games go either way; ATS record may be volatile.")
                else:
                    weaknesses.append(f"**Negative/flat efficiency margin ({net:+.1f})** — over-ranked by record; often flatters to deceive late.")

                # Relative weakness flag: find the worst category
                category_scores = {"Offense": oe / 113, "Defense": 99 / de, "3PT Rate": tpr / 0.37}
                worst_cat = min(category_scores, key=lambda k: category_scores[k])
                if not any(worst_cat.lower() in w.lower() for w in weaknesses):
                    if worst_cat == "Offense":
                        weaknesses.append(f"**Relative weak point — Offense** (OE {oe:.1f}): the lowest-rated facet of this team's game vs. peer programs.")
                    elif worst_cat == "Defense":
                        weaknesses.append(f"**Relative weak point — Defense** (DE {de:.1f}): the defensive end is where this team can be exploited.")
                    else:
                        weaknesses.append(f"**Relative weak point — Three-point shooting** ({tpr:.0%}): opponents that defend the arc well can stifle this team.")

                if strengths:
                    st.markdown("**✅ Strengths**")
                    for item in strengths:
                        st.markdown(f"- {item}")
                if weaknesses:
                    st.markdown("**⚠️ Weaknesses**")
                    for item in weaknesses:
                        st.markdown(f"- {item}")

                # Betting angle
                st.markdown("---")
                st.markdown("**💰 Betting Angle**")
                if net >= 12 and pace >= 70:
                    angle = "Best as a home favorite. First-half lines are attractive given their fast starts. Fades poorly in road second halves."
                elif de <= 98 and pace <= 65:
                    angle = "Strong underdog value in low-total games. Defensive efficiency keeps games close — target unders and +spread."
                elif tpr >= 0.40:
                    angle = "High-variance — target spread both directions off neutral courts. Prime live-bet candidate during cold shooting stretches."
                elif oe >= 112 and de >= 107:
                    angle = "Offensive juggernaut with a leaky defense. Overs are attractive vs. fast opponents. Spread prone to volatile openers."
                else:
                    angle = "No clear systematic edge identified. Evaluate each game's matchup and line movement individually."
                st.info(angle)

    # ─ Teams Grid page body ──────────────────────────────────────────────
    back_btn()
    st.markdown('<div class="page-title">🏀 Teams Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Click any team to view roster, schedule, and facts powered by ESPN</div>', unsafe_allow_html=True)

    # Pull dynamic list of 362 Div 1 teams
    all_teams_map = get_all_espn_teams()
    
    # Store all db stats for sorting lookups
    db_stats = {s.get("team_name", ""): s for s in ledger.get_all_team_stats()}
    db_ranks: dict[str, int] = {name: s.get("ranking") for name, s in db_stats.items() if s.get("ranking")}

    # Filter bar
    f1, f2 = st.columns([3, 1])
    search_q = f1.text_input("", placeholder="🔍 Search teams...", label_visibility="collapsed")
    sort_by = f2.selectbox("Sort by", ["AP Rank", "Alphabetical", "Offensive Efficiency", "Defensive Efficiency", "Pace"], label_visibility="collapsed")

    # Sort logic
    def sort_key(item):
        name, _ = item
        s = db_stats.get(name, {})
        rank = s.get("ranking")
        
        if sort_by == "AP Rank":
            return (0, rank) if rank else (1, name)
        elif sort_by == "Alphabetical":
            return name
        elif sort_by == "Offensive Efficiency":
            val = float(s.get("offensive_efficiency") or 0)
            return (0, -val) if val else (1, name)
        elif sort_by == "Defensive Efficiency":
            val = float(s.get("defensive_efficiency") or 0)
            # We want lowest defensive efficiency first, but prioritize teams that have stats (val > 0)
            return (0, val) if val else (1, name)
        elif sort_by == "Pace":
            val = float(s.get("pace") or 0)
            return (0, -val) if val else (1, name)
            
        return (0, rank) if rank else (1, name)

    sorted_teams = sorted(all_teams_map.items(), key=sort_key)

    if search_q:
        sorted_teams = [(n, i) for n, i in sorted_teams
                        if search_q.lower() in n.lower()]

    # Grid: 5 columns
    GRID_COLS = 5
    rows = [sorted_teams[i:i+GRID_COLS] for i in range(0, len(sorted_teams), GRID_COLS)]

    for row in rows:
        cols = st.columns(GRID_COLS)
        for col, (team_name, espn_id) in zip(cols, row):
            with col:
                rank = db_ranks.get(team_name)
                rank_badge = (
                    f'<div style="position:absolute;top:8px;left:8px;background:#f97316;'
                    f'color:white;font-size:.65rem;font-weight:900;padding:2px 7px;'
                    f'border-radius:20px">#{rank}</div>'
                ) if rank else ""

                card_html = f"""
<div style="position:relative;background:#111827;border:1px solid #1e2d45;
            border-radius:14px;padding:1rem .8rem;text-align:center;
            transition:border-color .2s;margin-bottom:.5rem">
  {rank_badge}
  <img src="{logo_url(espn_id)}" style="width:64px;height:64px;object-fit:contain"
       onerror="this.style.display='none'">
  <div style="font-size:.82rem;font-weight:700;margin-top:.5rem;line-height:1.2">
    {team_name.split()[0]} {team_name.split()[1] if len(team_name.split()) > 1 else ''}
  </div>
</div>"""
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button("View", key=f"team_{espn_id}", use_container_width=True):
                    show_team(team_name, espn_id, rank)
