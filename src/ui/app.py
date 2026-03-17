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
from src.models.schemas import BetType, BetSide
from src.tools.odds_client import get_live_games, _lookup_team_stats
from src.agents.ev_calculator import analyze_full_slate
from src.tools.espn_client import (
    fetch_team_summary, fetch_team_roster, fetch_team_schedule,
    fetch_best_worst, fetch_boxscore, fetch_player_stats,
    fetch_team_stat_leaders, fetch_game_venue, inches_to_ft,
    get_espn_team_id, logo_url, TEAM_ESPN_IDS, get_all_espn_teams, get_all_standings
)
from src.agents.batch_preview import generate_slate_previews, generate_team_scouting_report

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
THEMES = {
    "Default Dark": {
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
        "sidebar":   "linear-gradient(180deg, #0d1424 0%, #0a1020 100%)"
    },
    "Light": {
        "bg":        "#f8fafc",
        "surface":   "#ffffff",
        "surface2":  "#f1f5f9",
        "border":    "#e2e8f0",
        "accent":    "#ea580c",
        "gold":      "#d97706",
        "green":     "#16a34a",
        "red":       "#dc2626",
        "muted":     "#94a3b8",
        "text":      "#0f172a",
        "text2":     "#475569",
        "sidebar":   "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)"
    },
    "Monokai": {
        "bg":        "#272822",
        "surface":   "#3e3d32",
        "surface2":  "#49483e",
        "border":    "#1e1e1e",
        "accent":    "#fd971f",
        "gold":      "#e6db74",
        "green":     "#a6e22e",
        "red":       "#f92672",
        "muted":     "#75715e",
        "text":      "#f8f8f2",
        "text2":     "#cfcfc2",
        "sidebar":   "linear-gradient(180deg, #2c2d27 0%, #272822 100%)"
    },
    "Solarized Dark": {
        "bg":        "#002b36",
        "surface":   "#073642",
        "surface2":  "#586e75",
        "border":    "#001f27",
        "accent":    "#cb4b16",
        "gold":      "#b58900",
        "green":     "#859900",
        "red":       "#dc322f",
        "muted":     "#586e75",
        "text":      "#839496",
        "text2":     "#93a1a1",
        "sidebar":   "linear-gradient(180deg, #002b36 0%, #001f27 100%)"
    },
    "Solarized Light": {
        "bg":        "#fdf6e3",
        "surface":   "#eee8d5",
        "surface2":  "#93a1a1",
        "border":    "#d8d0b8",
        "accent":    "#cb4b16",
        "gold":      "#b58900",
        "green":     "#859900",
        "red":       "#dc322f",
        "muted":     "#93a1a1",
        "text":      "#657b83",
        "text2":     "#586e75",
        "sidebar":   "linear-gradient(180deg, #fdf6e3 0%, #eee8d5 100%)"
    }
}

if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "Default Dark"
    
COLORS = THEMES[st.session_state.ui_theme]

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
    background: {COLORS["sidebar"]} !important;
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

/* ── Main Buttons (Quick Actions) ── */
.main [data-testid="stButton"] > button[kind="secondary"] {{
    background: linear-gradient(135deg, rgba(26,34,54,0.6) 0%, rgba(17,24,39,0.8) 100%) !important;
    border: 1px solid {COLORS["border"]} !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
    transition: all 0.2s ease !important;
    padding: 1.2rem !important;
}}
.main [data-testid="stButton"] > button[kind="secondary"]:hover {{
    background: rgba(56,189,248,0.1) !important;
    border-color: {COLORS["accent"]} !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.5) !important;
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
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}

/* ── Sidebar Toggle Buttons (Collapse / Expand) ── */
button[kind="headerNoPadding"] {{
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
}}
button[kind="headerNoPadding"]:hover {{
    background: {COLORS["surface2"]} !important;
    transform: scale(1.1) !important;
}}
button[kind="headerNoPadding"] svg {{
    fill: {COLORS["accent"]} !important;
    color: {COLORS["accent"]} !important;
    width: 18px !important;
    height: 18px !important;
}}

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
.gc-tname {{ font-family:'Nunito',sans-serif; font-weight:800; font-size:.85rem; text-align:center; color:{COLORS["text"]}; line-height:1.25; }}
.gc-rec {{ font-size:.72rem; color:{COLORS["muted"]}; font-weight:600; }}
.gc-label {{ font-size:.62rem; color:#4b5563; font-weight:700; letter-spacing:.06em; text-transform:uppercase; }}
.gc-vs {{ font-family:'Nunito'; font-size:1rem; font-weight:900; color:#374151; padding:0 .5rem; }}
.gc-mid {{ flex:1; display:flex; flex-direction:column; gap:.4rem; }}
.gc-venue {{ font-size:.75rem; color:#60a5fa; font-weight:600; }}
.gc-spread {{ font-size:.75rem; color:#a3e635; font-weight:700; }}
.gc-leaders {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.3rem; }}
.gc-pill {{ background:rgba(255,255,255,.06); border-radius:7px; padding:.2rem .55rem; font-size:.7rem; color:#d1d5db; }}
.gc-pill b {{ color:{COLORS["accent"]}; }}
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
    "ai_previews": {},
    "live_game_bet_id": None,
    "live_game_info": None,
    "live_analysis_cache": {},
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
    nav_btn("🏆", "Tournament Predictor", "tourney")

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
  <div style="font-size:0.7rem;color:{COLORS['muted']};text-transform:uppercase;letter-spacing:.08em">Bankroll</div>
  <div style="font-size:1.6rem;font-weight:900;color:{COLORS['accent']}">{bankroll['balance_units']:.1f}u</div>
  <div style="font-size:0.8rem;color:{pl_color};margin-top:0.2rem">
    {"▲" if total_pl >= 0 else "▼"} {abs(total_pl):.2f}u all-time
  </div>
  <div style="font-size:0.8rem;color:{COLORS['muted']};margin-top:0.2rem">{wins}W – {losses}L</div>
</div>
""", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.7rem;color:#4b5563;text-align:center;margin-top:0.8rem'>{datetime.now().strftime('%b %d, %Y · %I:%M %p')}</div>", unsafe_allow_html=True)

    st.markdown("---")
    def on_theme_change():
        st.session_state.ui_theme = st.session_state._theme_select
        
    st.selectbox(
        "✨ Appearance", 
        options=list(THEMES.keys()), 
        index=list(THEMES.keys()).index(st.session_state.ui_theme),
        key="_theme_select",
        on_change=on_theme_change,
        label_visibility="collapsed"
    )

    st.markdown("""
<div style="font-size:0.65rem; color:#4b5563; text-align:center; padding-top:1rem; padding-bottom:1rem;">
  Data powered by ESPN & Odds APIs<br>
  Built for autonomous +EV hunting
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":
    today = datetime.now().strftime("%A, %B %d %Y")
    pending_bets: list[dict] = list(ledger.db["bets"].rows_where("status IN ('pending','approved')", []))
    pending_parlays: list[dict] = ledger.get_pending_parlays()
    total_pending = len(pending_bets) + len(pending_parlays)
    ev_bets: list[dict] = [b for b in pending_bets if b.get("status") == "approved"]
    pl_sign = "+" if total_pl >= 0 else ""

    # ── INDIE HERO ──────────────────────────────────────────────
    st.markdown(f"""
<div class="indie-hero">
  <div class="indie-title">🏀 Hoops Edge</div>
  <div class="indie-sub">AI-Powered Basketball Insights</div>
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
    # ── CHECK FOR ACTION REQUIRED BUILDUP ────────────────────────
    action_required_count: int = 0
    if total_pending > 0:
        with st.spinner("Checking for unsettled final games..."):
            try:
                # Reuse cached live games if possible
                if st.session_state.all_games is None:
                    st.session_state.all_games = get_live_games(ledger)
                
                final_game_matchups = set()
                for g in st.session_state.all_games:
                    if g.status == "STATUS_FINAL":
                        final_game_matchups.add(f"{g.away_team} @ {g.home_team}")
                
                # Check bets
                for b in pending_bets:
                    m = f"{b['away_team']} @ {b['home_team']}"
                    if m in final_game_matchups:
                        action_required_count += 1
                        
                # Check parlays (simplified, if any leg is final, prompt user to check)
                for p in pending_parlays:
                    try:
                        legs = json.loads(p.get("leg_ids", "[]"))
                        if any(l in final_game_matchups for l in legs):
                            action_required_count += 1
                    except:
                        pass
            except Exception as e:
                print(f"Silently continuing if scoreboard fails: {e}")

    pending_desc = f"{total_pending} ticket(s) awaiting action"
    if action_required_count > 0:
        pending_desc = f'<span style="color:#ef4444;font-weight:800">🔴 ACTION REQUIRED: Settle {action_required_count} bet(s)</span>'
        
    actions = [
        (row1[0], "home_slate",   "slate",   "📋", "Today's Slate",   "Live lines → Pick games → Find edges"),
        (row1[1], "home_picks",   "picks",   "📊", "Picks & Analysis","See all AI bet suggestions"),
        (row1[2], "home_pending", "pending", "⏳", "Pending Bets",   pending_desc),
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
        st.markdown('<div style="font-size:.8rem;color:#9ca3af;margin-bottom:.5rem">Click any bet to view live score & AI analysis</div>', unsafe_allow_html=True)
        for b in ev_bets[:5]:
            bet_label = (
                f"{'🏀'} {b['away_team']} @ {b['home_team']}\n"
                f"{b['bet_type'].upper()} {b['side'].upper()} · EV {b['expected_value']:+.1%} · {b['recommended_units']:.2f}u"
            )
            if st.button(bet_label, key=f"live_btn_{b['id'][:8]}", use_container_width=True):
                st.session_state.live_game_bet_id = b["id"]
                st.session_state.page = "live_game"
                st.rerun()

    # ── INSIGHTFUL ADDITIONS (HOT TEAMS & TIP) ──────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="indie-section-hdr">🔥 Quant Metrics (Top NCAAB Performers)</div>', unsafe_allow_html=True)
    
    all_stats = ledger.get_all_team_stats()
    if all_stats:
        # Filter for valid data
        valid_off = [t for t in all_stats if t.get('offensive_efficiency') and t['offensive_efficiency'] > 0]
        valid_def = [t for t in all_stats if t.get('defensive_efficiency') and t['defensive_efficiency'] > 0]
        valid_pace = [t for t in all_stats if t.get('pace') and t['pace'] > 0]
        valid_3pt = [t for t in all_stats if t.get('three_point_rate') and t['three_point_rate'] > 0]
        
        top_offense = sorted(valid_off, key=lambda x: x['offensive_efficiency'], reverse=True)[:3]
        top_defense = sorted(valid_def, key=lambda x: x['defensive_efficiency'])[:3]
        top_pace = sorted(valid_pace, key=lambda x: x['pace'], reverse=True)[:3]
        top_shooting = sorted(valid_3pt, key=lambda x: x['three_point_rate'], reverse=True)[:3]
        
        # Row 1: Offense & Defense
        c_off, c_def = st.columns(2)
        with c_off:
            st.markdown('<div style="font-size:0.9rem;color:#94a3b8;margin-bottom:0.5rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Top Offenses (AdjO)</div>', unsafe_allow_html=True)
            for i, t in enumerate(top_offense, 1):
                st.markdown(f"""<div class="glass-card" style="padding:0.75rem 1rem; margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">
                    <span><b style="color:{COLORS['accent']};margin-right:0.4rem;">{i}.</b> {t['team_name']}</span>
                    <span style="color:#f8fafc; font-weight:700;">{t['offensive_efficiency']:.1f}</span>
                </div>""", unsafe_allow_html=True)
                
        with c_def:
            st.markdown('<div style="font-size:0.9rem;color:#94a3b8;margin-bottom:0.5rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Top Defenses (AdjD)</div>', unsafe_allow_html=True)
            for i, t in enumerate(top_defense, 1):
                st.markdown(f"""<div class="glass-card" style="padding:0.75rem 1rem; margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">
                    <span><b style="color:{COLORS['green']};margin-right:0.4rem;">{i}.</b> {t['team_name']}</span>
                    <span style="color:#f8fafc; font-weight:700;">{t['defensive_efficiency']:.1f}</span>
                </div>""", unsafe_allow_html=True)

        # Row 2: Pace & 3PT Shooting
        c_pace, c_3pt = st.columns(2)
        with c_pace:
            st.markdown('<div style="font-size:0.9rem;color:#94a3b8;margin-bottom:0.5rem;margin-top:1rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Top Scorers (Pace)</div>', unsafe_allow_html=True)
            for i, t in enumerate(top_pace, 1):
                st.markdown(f"""<div class="glass-card" style="padding:0.75rem 1rem; margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">
                    <span><b style="color:#f59e0b;margin-right:0.4rem;">{i}.</b> {t['team_name']}</span>
                    <span style="color:#f8fafc; font-weight:700;">{t['pace']:.1f}</span>
                </div>""", unsafe_allow_html=True)
                
        with c_3pt:
            st.markdown('<div style="font-size:0.9rem;color:#94a3b8;margin-bottom:0.5rem;margin-top:1rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Top Assists (3PT Rate)</div>', unsafe_allow_html=True)
            for i, t in enumerate(top_shooting, 1):
                st.markdown(f"""<div class="glass-card" style="padding:0.75rem 1rem; margin-bottom:0.4rem; display:flex; justify-content:space-between; align-items:center;">
                    <span><b style="color:#8b5cf6;margin-right:0.4rem;">{i}.</b> {t['team_name']}</span>
                    <span style="color:#f8fafc; font-weight:700;">{t['three_point_rate']:.0%}</span>
                </div>""", unsafe_allow_html=True)

    # Fun AI Tip Widget
    import random
    tips = [
        "The journey of a thousand miles begins with a single step.",
        "Fortune favors the bold — but wisdom favors the patient.",
        "A smooth sea never made a skilled sailor.",
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "In the middle of difficulty lies opportunity.",
        "What you do today can improve all your tomorrows.",
        "Success is not final, failure is not fatal — it is the courage to continue that counts.",
        "The only way to do great work is to love what you do.",
        "Be yourself; everyone else is already taken.",
        "Stars can't shine without darkness.",
        "Every expert was once a beginner.",
        "The harder you work, the luckier you get.",
    ]
    todays_tip = random.choice(tips)
    
    st.markdown(f"""
    <div style="margin-top:1.5rem; background: linear-gradient(to right, rgba(139, 92, 246, 0.1), transparent); border-left: 4px solid #8b5cf6; padding: 1rem 1.5rem; border-radius: 0 8px 8px 0;">
        <div style="font-size:0.8rem; color:#a78bfa; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:0.3rem;">🪄 Daily Wisdom</div>
        <div style="color:#e2e8f0; font-size:1.05rem; font-style:italic;">"{todays_tip}"</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SLATE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "slate":
    back_btn()
    st.markdown('<div class="page-title">📋 Today\'s Slate</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Select leagues, load live FanDuel lines, check the games you want, then run EV analysis</div>', unsafe_allow_html=True)

    # ── LEAGUE SELECTION ──────────────────────────────────────────────
    c_l1, c_l2, c_l3 = st.columns(3)
    with c_l1:
        st.session_state.setdefault("sel_ncaab", True)
        st.checkbox("NCAAB (Men's College)", key="sel_ncaab")
    with c_l2:
        st.session_state.setdefault("sel_ncaaw", False)
        st.checkbox("NCAAW (Women's College)", key="sel_ncaaw")
    with c_l3:
        st.session_state.setdefault("sel_nba", False)
        st.checkbox("NBA (Professional)", key="sel_nba")

    if st.button("📥 Load Today's Games", type="primary"):
        # Compile requested sports
        sport_keys = []
        if st.session_state.sel_ncaab: sport_keys.append("basketball_ncaab")
        if st.session_state.sel_ncaaw: sport_keys.append("basketball_ncaaw")
        if st.session_state.sel_nba: sport_keys.append("basketball_nba")
        
        if not sport_keys:
            st.warning("Please select at least one league to load games.")
        else:
            with st.spinner(f"Fetching live FanDuel odds for {len(sport_keys)} league(s)..."):
                try:
                    games = get_live_games(ledger, sport_keys=sport_keys)
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
            {len(all_games)} games loaded · ⭐ = stats in DB · #N = AP rank
            </div>""", unsafe_allow_html=True)

        if "game_checks" not in st.session_state:
            st.session_state.game_checks = {}

        # ── FILTERS ───────────────────────────────────────────────────────────
        ALL_D1_CONFS = [
            "America East", "American", "ASUN", "Atlantic 10", "ACC", "Big 12", "Big East", 
            "Big Sky", "Big South", "Big Ten", "Big West", "CAA", "CUSA", "Horizon", 
            "Ivy", "MAAC", "MAC", "MEAC", "Missouri Valley", "Mountain West", "NEC", 
            "OVC", "Patriot", "SEC", "SoCon", "Southland", "SWAC", "Summit", "Sun Belt", 
            "WAC", "WCC"
        ]
        with st.expander("⚙️ Filter Games", expanded=True):
            f_cols = st.columns(4)
            with f_cols[0]:
                filter_conf = st.multiselect("Conferences (Select multiple)", options=["Power 5", "Mid-Major"] + ALL_D1_CONFS, default=[])
            with f_cols[1]:
                filter_ranked = st.checkbox("Ranked Teams Only", value=False)
            with f_cols[2]:
                filter_wins = st.slider("Min Wins (Either Team)", min_value=0, max_value=30, value=0)
            with f_cols[3]:
                st.session_state.selected_book = st.selectbox("Sportsbook", options=["fanduel", "draftkings", "betmgm", "caesars"], index=0)
                
            filter_spread = st.slider("Max Spread (Absolute Value)", min_value=0.0, max_value=40.0, value=40.0, step=0.5, help="Filter out heavily lopsided matchups.")

        # Apply filters
        POWER_5 = {"SEC", "ACC", "Big 12", "Big Ten", "Big East"}
        filtered_games = []
        for g in sorted_games:
            # Rank filter
            is_ranked = (g.home_stats and g.home_stats.ranking) or (g.away_stats and g.away_stats.ranking)
            if filter_ranked and not is_ranked:
                continue
                
            # Conference filter
            standings = get_all_standings(g.sport_key)
            home_conf_api = standings.get(g.home_team, {}).get("conference", "")
            away_conf_api = standings.get(g.away_team, {}).get("conference", "")
            
            home_conf = home_conf_api or (g.home_stats.conference if g.home_stats and g.home_stats.conference else "")
            away_conf = away_conf_api or (g.away_stats.conference if g.away_stats and g.away_stats.conference else "")
            
            if filter_conf:
                valid_conf = False
                matched_confs = set(filter_conf)
                
                home_is_p5 = home_conf in POWER_5
                away_is_p5 = away_conf in POWER_5
                
                # Check Power 5
                if "Power 5" in matched_confs:
                    if home_is_p5 or away_is_p5:
                        valid_conf = True
                
                # Check Mid-Major
                if "Mid-Major" in matched_confs:
                    if not home_is_p5 or not away_is_p5:
                        valid_conf = True
                        
                # Check specific individual conferences
                if home_conf in matched_confs or away_conf in matched_confs:
                    valid_conf = True
                    
                if not valid_conf:
                    continue
                
            # Win filter
            def get_wins(record: str) -> int:
                try: return int(record.split("-")[0])
                except: return 0
                
            hw = get_wins(g.home_stats.record) if g.home_stats else 0
            aw = get_wins(g.away_stats.record) if g.away_stats else 0
            if max(hw, aw) < filter_wins:
                continue
                
            # Spread filter
            book = st.session_state.get("selected_book", "fanduel")
            if g.home_odds and book in g.home_odds:
                s = g.home_odds[book].line
                if s is not None and abs(s) > filter_spread:
                    continue
                
            filtered_games.append(g)

        # ── TOP CONTROL BAR ───────────────────────────────────────────────────
        selected_ids = [gid for gid, v in st.session_state.game_checks.items() if v]
        n_sel = len(selected_ids)
        c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
        with c1:
            st.markdown(f"**Showing {len(filtered_games)} games** (Selected {n_sel} for analysis).")
        with c2:
            if len(filtered_games) > 0:
                if st.button("☑️ Select All", use_container_width=True):
                    for g in filtered_games:
                        gid = g.game_id if g.game_id else f"game_{all_games.index(g)}"
                        st.session_state.game_checks[gid] = True
                    st.rerun()
                if n_sel > 0:
                    if st.button("🔳 Deselect All", use_container_width=True):
                        st.session_state.game_checks.clear()
                        st.rerun()
        with c3:
            if n_sel > 0:
                if st.button(f"🪄 AI Previews ({n_sel})", use_container_width=True):
                    chosen = [g for g in all_games if g.game_id in selected_ids]
                    with st.spinner(f"Generating mini-previews for {len(chosen)} game(s)..."):
                        try:
                            book = st.session_state.get("selected_book", "fanduel")
                            previews = run_async(generate_slate_previews(chosen, bookmaker=book))
                            # Merge into existing so we don't lose old ones if filtering changes
                            st.session_state.ai_previews.update(previews)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Preview error: {e}")
        with c4:
            if n_sel > 0:
                if st.button(f"▶ Analyze {n_sel} Game{'s' if n_sel != 1 else ''}", type="primary", use_container_width=True):
                    chosen = [g for g in all_games if g.game_id in selected_ids]
                    with st.spinner(f"🤖 Running EV analysis on {len(chosen)} game(s)..."):
                        try:
                            book = st.session_state.get("selected_book", "fanduel")
                            slate = run_async(analyze_full_slate(chosen, max_games=len(chosen), ledger=ledger, bookmaker=book))
                            st.session_state.slate = slate
                            st.session_state.slate_error = None
                            st.session_state.page = "picks"
                            st.rerun()
                        except Exception as e:
                            st.session_state.slate_error = str(e)
                            st.error(str(e))

        st.markdown("---")

        # ── GRID / LIST RENDERING ─────────────────────────────────────────────
        if not filtered_games:
            st.info("No games match your current filters. Try relaxing them.")
        else:
            for i, g in enumerate(filtered_games):
                away_name  = g.away_team
                home_name  = g.home_team
                away_rank  = g.away_stats.ranking if g.away_stats else None
                home_rank  = g.home_stats.ranking if g.home_stats else None
                away_rec   = g.away_stats.record if g.away_stats else ""
                home_rec   = g.home_stats.record if g.home_stats else ""
                tip        = g.game_time.strftime("%b %d, %I:%M %p ET") if g.game_time else "TBD"
                
                away_espn_id = get_espn_team_id(away_name, g.sport_key)
                home_espn_id = get_espn_team_id(home_name, g.sport_key)
                away_logo = logo_url(away_espn_id, g.sport_key) if away_espn_id else ""
                home_logo = logo_url(home_espn_id, g.sport_key) if home_espn_id else ""

                rank_badge_a = f'<div class="gc-rank">#{away_rank} AP</div>' if away_rank else ""
                rank_badge_h = f'<div class="gc-rank">#{home_rank} AP</div>' if home_rank else ""
                logo_tag_a   = f'<img src="{away_logo}" width="50" height="50" style="object-fit:contain" alt="{away_name}">' if away_logo else f'<div style="width:50px;height:50px;background:#1a2236;border-radius:8px;"></div>'
                logo_tag_h   = f'<img src="{home_logo}" width="50" height="50" style="object-fit:contain" alt="{home_name}">' if home_logo else f'<div style="width:50px;height:50px;background:#1a2236;border-radius:8px;"></div>'

                blurb_html = generate_matchup_bullets(g, tip)
                ai_prev = st.session_state.ai_previews.get(g.game_id, "")
                if ai_prev:
                    blurb_html += f'<div style="margin-top:0.5rem; padding-top:0.5rem; border-top:1px solid #1e2d45; color:#a78bfa;"><b>🪄 AI Edge:</b> {ai_prev}</div>'

                # True Implied Probability Visualization
                book = st.session_state.get("selected_book", "fanduel")
                true_home_p = g.get_true_implied_probability(BetType.MONEYLINE, BetSide.HOME, book)
                prob_bar_html = ""
                if true_home_p is not None:
                    true_away_p = 1.0 - true_home_p
                    h_pct = true_home_p * 100
                    a_pct = true_away_p * 100
                    
                    prob_bar_html = f"""<div style="margin-top:0.8rem; background: rgba(0,0,0,0.2); padding: 0.6rem; border-radius: 8px;">
<div style="display:flex;justify-content:space-between;font-size:0.68rem;color:#94a3b8;margin-bottom:0.3rem;font-weight:700;">
<span>{a_pct:.1f}%</span>
<span style="font-size:0.55rem;letter-spacing:0.05em;color:#64748b;">TRUE PROBABILITY (NO-VIG)</span>
<span>{h_pct:.1f}%</span>
</div>
<div style="width:100%;height:8px;background:#1e293b;border-radius:4px;overflow:hidden;display:flex;">
<div style="width:{a_pct}%;height:100%;background:{COLORS['accent']};transition:width 1s ease-in-out;"></div>
<div style="width:{h_pct}%;height:100%;background:{COLORS['green']};transition:width 1s ease-in-out;"></div>
</div>
</div>"""

                html_card = f"""
<div class="game-card" style="margin-bottom:0.8rem; padding:1rem;">
<div class="gc-teams" style="gap:0.8rem;">
<div class="gc-team" style="min-width:80px;">
{logo_tag_a}
{rank_badge_a}
<div class="gc-tname">{away_name}</div>
<div class="gc-rec">{away_rec}</div>
</div>
<div class="gc-vs">@</div>
<div class="gc-team" style="min-width:80px;">
{logo_tag_h}
{rank_badge_h}
<div class="gc-tname">{home_name}</div>
<div class="gc-rec">{home_rec}</div>
</div>
<div class="gc-mid" style="flex:2;">
<div style="font-size:.75rem;color:#fbbf24;font-weight:800;margin-bottom:0.2rem">{tip}</div>
<div style="font-size:0.75rem;color:#cbd5e1;line-height:1.4;">{blurb_html}</div>
{prob_bar_html}
</div>
</div>
</div>
"""
                st.markdown(html_card, unsafe_allow_html=True)
                
                # Checkbox for selection underneath each card inline
                gid = g.game_id if g.game_id else f"game_{i}"
                checked = st.session_state.game_checks.get(gid, False)
                _chk_col, _watch_col = st.columns([4, 1])
                with _chk_col:
                    new_val = st.checkbox(f"Analyze {away_name} @ {home_name}", value=checked, key=f"chk_{gid}")
                    if new_val != checked:
                        st.session_state.game_checks[gid] = new_val
                        st.rerun()
                with _watch_col:
                    if st.button("📡", key=f"watch_{gid}", help="View live score & AI analysis"):
                        st.session_state.live_game_bet_id = None
                        st.session_state.live_game_info = {
                            "away": g.away_team, "home": g.home_team,
                            "sport": g.sport_key, "away_name": away_name, "home_name": home_name
                        }
                        st.session_state.page = "live_game"
                        st.rerun()

        st.markdown("")
    else:
        # Fetch bankroll and performance stats for Hero dashboard
        br = ledger.get_bankroll()
        settled = list(ledger.db["bets"].rows_where("status = ?", ["settled"]))
        settled_parlays = list(ledger.db["parlays"].rows_where("status = ?", ["settled"]))
        wins   = sum(1 for b in settled if b["result"] == "win") + sum(1 for p in settled_parlays if p["result"] == "win")
        losses = sum(1 for b in settled if b["result"] == "loss") + sum(1 for p in settled_parlays if p["result"] == "loss")
        total_bets = wins + losses
        win_rate = (wins / total_bets) * 100 if total_bets > 0 else 0
        
        profit = sum(b["profit_loss"] for b in settled if b["profit_loss"] is not None) + \
                 sum(p["profit_loss"] for p in settled_parlays if p["profit_loss"] is not None)
        profit_color = COLORS["green"] if profit >= 0 else COLORS["red"]
        profit_sign = "+" if profit >= 0 else ""

        st.html(f"""
        <div class="hero" style="padding:3rem 2rem; margin-top:1rem; border-radius:16px; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 1px solid {COLORS['border']}; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
            <h1 style="font-size:2.5rem; margin-bottom:0.5rem; font-weight:800; background: -webkit-linear-gradient(45deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Welcome to Hoops Edge</h1>
            <p style="color:{COLORS['muted']}; font-size:1.1rem; margin-bottom:2.5rem; max-width:650px; margin-left:auto; margin-right:auto; line-height: 1.6;">
                Your AI-powered quantitative sports betting terminal. We combine live dynamic odds from leading bookmakers with sophisticated modeling to hunt for positive Expected Value (+EV) opportunities.
            </p>
            
            <div style="display:flex; justify-content:center; gap:1.5rem; flex-wrap:wrap; margin-bottom:2.5rem;">
                <div style="background: rgba(0,0,0,0.3); padding:1.5rem 2rem; border-radius:12px; border: 1px solid rgba(255,255,255,0.05); min-width: 160px; backdrop-filter: blur(4px);">
                    <div style="font-size:0.75rem; color:{COLORS['muted']}; text-transform:uppercase; letter-spacing:1px; margin-bottom:0.5rem; font-weight: 600;">Bankroll</div>
                    <div style="font-size:2.2rem; font-weight:700; color: #f8fafc;">{br['balance_units']:.2f}u</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding:1.5rem 2rem; border-radius:12px; border: 1px solid rgba(255,255,255,0.05); min-width: 160px; backdrop-filter: blur(4px);">
                    <div style="font-size:0.75rem; color:{COLORS['muted']}; text-transform:uppercase; letter-spacing:1px; margin-bottom:0.5rem; font-weight: 600;">Net Profit</div>
                    <div style="font-size:2.2rem; font-weight:700; color:{profit_color};">{profit_sign}{profit:.2f}u</div>
                </div>
                <div style="background: rgba(0,0,0,0.3); padding:1.5rem 2rem; border-radius:12px; border: 1px solid rgba(255,255,255,0.05); min-width: 160px; backdrop-filter: blur(4px);">
                    <div style="font-size:0.75rem; color:{COLORS['muted']}; text-transform:uppercase; letter-spacing:1px; margin-bottom:0.5rem; font-weight: 600;">Win Rate</div>
                    <div style="font-size:2.2rem; font-weight:700; color:{COLORS['accent']};">{win_rate:.1f}%</div>
                </div>
            </div>

            <div style="background: rgba(56, 189, 248, 0.05); border: 1px dashed rgba(56, 189, 248, 0.3); padding: 1.5rem; border-radius: 12px; display:inline-block; max-width: 500px;">
                <div style="font-size:1.8rem; margin-bottom:0.5rem;">⚡</div>
                <div style="font-weight:600; color:#e2e8f0; margin-bottom:0.3rem;">Ready to find edges?</div>
                <div style="color:{COLORS['muted']}; font-size:0.95rem;">Select your leagues above and click <b>Load Today's Games</b> to pull the latest sportsbook odds.</div>
            </div>
        </div>
        """)


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
                tip = rec.game_time.strftime("%b %d, %I:%M %p ET") if rec.game_time else ""
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

    # ── Auto Settle ──────────────────────────────────────────────────────────
    if pending:
        from src.tools.settlement import auto_settle_pending_bets
        if st.button("🔄 Auto-Settle Completed Games via ESPN", use_container_width=True):
            with st.spinner("Scanning ESPN Scoreboard for final scores..."):
                w, l, p = auto_settle_pending_bets(ledger)
                if w > 0 or l > 0 or p > 0:
                    st.success(f"Auto-Settle Complete: {w} Wins, {l} Losses, {p} Pushes!")
                else:
                    st.info("No pending single bets match any recently finalized ESPN games.")
            import time
            time.sleep(2)
            st.rerun()

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
                    f"({'%+d' % bet['american_odds']})  ·  EV {bet['expected_value']:+.1%}  ·  "
                    f"Conviction: {bet.get('kelly_multiplier', 0.25):.2f}x  ·  {bet['recommended_units']:.2f}u"
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
                    pl = sc2.number_input("P/L (units)", value=float(bet["recommended_units"]),
                                               step=0.01, key=f"pl_{bet['id'][:8]}")
                if sc3.button("Settle", key=f"st_{bet['id'][:8]}"):
                    pl_val = float(pl)
                    ledger.settle_bet(bet["id"], result, pl_val if result != "loss" else -abs(pl_val))
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
                    pl = psc2.number_input("P/L (units)", value=float(p["recommended_units"]),
                                               step=0.01, key=f"ppl_{p['id'][:8]}")
                    if psc3.button("Settle", key=f"pst_{p['id'][:8]}"):
                        pl_val = float(pl)
                        ledger.settle_parlay(p["id"], result, pl_val if result != "loss" else -abs(pl_val))
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
    
    # Pre-fetch team conferences from the ledger (synced via seed_teams.py)
    team_confs = {row["team_name"]: row["conference"] for row in ledger.db["team_stats"].rows}
    POWER_5 = {"SEC", "ACC", "Big 12", "Big Ten", "Big East"}
    
    # ── PERFORMANCE FILTERS ───────────────────────────────────────────────────
    ALL_D1_CONFS = [
        "America East", "American", "ASUN", "Atlantic 10", "ACC", "Big 12", "Big East", 
        "Big Sky", "Big South", "Big Ten", "Big West", "CAA", "CUSA", "Horizon", 
        "Ivy", "MAAC", "MAC", "MEAC", "Missouri Valley", "Mountain West", "NEC", 
        "OVC", "Patriot", "SEC", "SoCon", "Southland", "SWAC", "Summit", "Sun Belt", 
        "WAC", "WCC"
    ]
    with st.expander("⚙️ Filter Performance History", expanded=True):
        perf_filter_conf = st.multiselect("Conferences (Select multiple)", options=["Power 5", "Mid-Major"] + ALL_D1_CONFS, default=[], key="perf_conf_filter")

    settled_all = settled + settled_parlays
    
    # Apply filters
    filtered_settled = []
    for b in settled_all:
        home_conf = team_confs.get(b.get('home_team', ''), "")
        away_conf = team_confs.get(b.get('away_team', ''), "")
        
        if perf_filter_conf:
            valid_conf = False
            matched_confs = set(perf_filter_conf)
            
            home_is_p5 = home_conf in POWER_5
            away_is_p5 = away_conf in POWER_5
            
            # Check Power 5
            if "Power 5" in matched_confs:
                if home_is_p5 or away_is_p5:
                    valid_conf = True
            
            # Check Mid-Major
            if "Mid-Major" in matched_confs:
                if not home_is_p5 or not away_is_p5:
                    valid_conf = True
                    
            # Check specific individual conferences
            if home_conf in matched_confs or away_conf in matched_confs:
                valid_conf = True
                
            if not valid_conf:
                continue
                
        filtered_settled.append(b)
    
    if filtered_settled:
        st.markdown('<div class="page-title" style="font-size:1.1rem">📊 Bankroll Trend</div>', unsafe_allow_html=True)
        # Sort chronologically by created date
        sorted_settled = sorted(filtered_settled, key=lambda x: x.get("created_at", ""))
        cum_pl = 0.0
        history_data = [{"Bet": 0, "Cumulative P/L (Units)": 0.0}]
        
        daily_pl = {}
        daily_count = {}
        
        for i, b in enumerate(sorted_settled, 1):
            if b.get("profit_loss") is not None:
                pl = b["profit_loss"]
                cum_pl += pl
                
                # Extract date string for calendar
                dr = b.get("created_at", "")
                if dr:
                    day_str = dr[:10]
                    daily_pl[day_str] = daily_pl.get(day_str, 0.0) + pl
                    daily_count[day_str] = daily_count.get(day_str, 0) + 1
                    
            history_data.append({"Bet": i, "Cumulative P/L (Units)": cum_pl})
            
        st.line_chart(history_data, x="Bet", y="Cumulative P/L (Units)", use_container_width=True, color="#22c55e")
        
        # --- Calendar Heatmap ---
        if daily_pl:
            st.markdown('<div class="page-title" style="font-size:1.1rem; margin-top:2rem;">📅 Profit/Loss Heatmap (Last 30 Days)</div>', unsafe_allow_html=True)
            from datetime import timedelta
            today = datetime.now().date()
            start_date = today - timedelta(days=29)
            
            # CSS for calendar grid and custom tooltips (Unindented to prevent markdown code blocks)
            grid_html = (
"<style>"
".cal-container { width: 100%; max-width: 800px; margin: 0 auto 2rem auto; }"
".cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }"
".cal-header { text-align: center; font-size: 0.75rem; font-weight: 700; color: #94a3b8; margin-bottom: 4px; padding: 4px 0; text-transform: uppercase; letter-spacing: 0.05em; }"
".cal-cell { position: relative; height: 64px; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 0.85rem; cursor: pointer; color: rgba(255,255,255,0.9); border: 1px solid #334155; transition: transform 0.1s, filter 0.1s; }"
".cal-cell:hover { filter: brightness(1.2); transform: scale(1.03); z-index: 2; }"
".cal-cell-empty { background: transparent; border: none; pointer-events: none; }"
".cal-day { font-weight: 700; font-size: 0.9rem; margin-bottom: 2px; }"
".cal-pl { font-size: 0.65rem; font-weight: 600; opacity: 0.9; }"
".cal-tooltip { visibility: hidden; opacity: 0; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: #0f172a; color: #f8fafc; padding: 8px 12px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; z-index: 50; border: 1px solid #334155; pointer-events: none; transition: opacity 0.2s; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5); text-align: center; }"
".cal-tooltip::after { content: ''; position: absolute; top: 100%; left: 50%; margin-left: -5px; border-width: 5px; border-style: solid; border-color: #334155 transparent transparent transparent; }"
".cal-cell:hover .cal-tooltip { visibility: visible; opacity: 1; }"
"</style>"
"<div class='cal-container'>"
"<div class='cal-grid'>"
            )
            
            # Days of week headers
            for day in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
                grid_html += f"<div class='cal-header'>{day}</div>"
                
            # Pad beginning of grid to align with correct weekday (Sunday = 0)
            start_day_idx = (start_date.weekday() + 1) % 7
            for _ in range(start_day_idx):
                grid_html += "<div class='cal-cell cal-cell-empty'></div>"
            
            max_p = max([p for p in daily_pl.values() if p > 0] + [0.1])
            min_l = min([p for p in daily_pl.values() if p < 0] + [-0.1])
            
            for i in range(30):
                d = start_date + timedelta(days=i)
                d_str = d.strftime("%Y-%m-%d")
                
                pl = daily_pl.get(d_str, 0.0)
                count = daily_count.get(d_str, 0)
                
                if pl > 0:
                    intensity = min(1.0, pl / max_p)
                    bg = f"rgba(34, 197, 94, {max(0.25, intensity)})"
                    border = f"rgba(34, 197, 94, {min(1.0, intensity + 0.3)})"
                    pl_text = f"+{pl:.2f}u"
                elif pl < 0:
                    intensity = min(1.0, abs(pl) / abs(min_l))
                    bg = f"rgba(239, 68, 68, {max(0.25, intensity)})"
                    border = f"rgba(239, 68, 68, {min(1.0, intensity + 0.3)})"
                    pl_text = f"{pl:.2f}u"
                else:
                    bg = "#1e293b"
                    border = "#334155"
                    pl_text = "-"
                    
                tooltip_date = d.strftime('%b %d, %Y')
                tooltip_body = f"<b>{pl:+.2f} Units</b><br>{count} bets settled" if count > 0 else "No settled bets"
                
                # Render cell
                grid_html += (
f"<div class='cal-cell' style='background-color: {bg}; border-color: {border};'>"
f"<div class='cal-day'>{d.day}</div>"
f"<div class='cal-pl'>{pl_text}</div>"
f"<div class='cal-tooltip'>"
f"<div style='color:#94a3b8;margin-bottom:3px'>{tooltip_date}</div>"
f"<div>{tooltip_body}</div>"
f"</div>"
f"</div>"
                )
                
            grid_html += "</div></div>"
            st.markdown(grid_html, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

    c_sb1, c_sb2 = st.columns([3, 1])
    with c_sb1:
        st.markdown('<div class="page-title" style="font-size:1.1rem">📜 Settled Bets</div>', unsafe_allow_html=True)
        
    with c_sb2:
        import csv, io
        if settled_all:
            output = io.StringIO()
            if len(settled_all) > 0:
                keys = list(dict(settled_all[0]).keys())
                writer = csv.DictWriter(output, fieldnames=keys)
                writer.writeheader()
                for r in settled_all:
                    writer.writerow(dict(r))
            csv_data = output.getvalue().encode('utf-8')
            st.download_button(
                label="📥 Export Ledger to CSV",
                data=csv_data,
                file_name=f"hoops_edge_ledger_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
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

        st.markdown('<div class="page-title" style="font-size:1.1rem;margin-top:2rem">🧠 AI Post-Mortem Analysis</div>', unsafe_allow_html=True)
        st.markdown("Select a settled bet to have the AI grade its original reasoning against the final game outcome.")
        
        c1, c2 = st.columns([3, 1])
        pm_options = {f"{b['away_team']} @ {b['home_team']} ({b['bet_type'].upper()} {b['side'].upper()} | {b['result'].upper()})": b for b in settled}
        if pm_options:
            selected_pm = c1.selectbox("Settled Bet", options=list(pm_options.keys()), label_visibility="collapsed")
            if c2.button("Grade Bet", use_container_width=True):
                b = pm_options[selected_pm]
                with st.spinner("Fetching final box score and analyzing..."):
                    try:
                        from src.tools.espn_client import fetch_team_schedule, get_espn_team_id, TEAM_ESPN_IDS
                        from src.agents.post_mortem import generate_post_mortem
                        
                        hid = get_espn_team_id(b.get("home_team", "")) or next((eid for n, eid in TEAM_ESPN_IDS.items() if any(w in b.get("home_team", "") for w in n.split()[:2])), None)
                        
                        final_ctx = "Score not found."
                        if hid:
                            comp = [e for e in fetch_team_schedule(hid) if e.get("completed")]
                            recent = comp[-3:] if len(comp) > 3 else comp
                            strs = []
                            for e in recent:
                                is_home = e.get("team_is_home", True)
                                ts = e.get("home_score") if is_home else e.get("away_score")
                                os = e.get("away_score") if is_home else e.get("home_score")
                                on = e.get("away") if is_home else e.get("home")
                                strs.append(f"{ts}-{os} vs {on} on {e.get('date','')}")
                            if strs:
                                final_ctx = " | ".join(strs)
                                
                        matchup = f"{b.get('away_team','')} @ {b.get('home_team','')}"
                        market = f"{b.get('bet_type','').upper()} {b.get('side','').upper()} ({b.get('american_odds',0):+d})"
                        rationale = b.get("summary", "No rationale recorded.")
                        res = b.get("result", "")
                        
                        pm_text = run_async(generate_post_mortem(matchup, market, rationale, res, final_ctx))
                        st.info(pm_text)
                    except Exception as e:
                        st.error(f"Error generating post-mortem: {e}")

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
                    tip = g.game_time.strftime("%b %d, %I:%M %p ET")
                    book = st.session_state.get("selected_book", "fanduel")
                    ho = g.home_odds.get(book)
                    spread = f"{g.home_team.split()[0]} {ho.line:+.1f}" if ho and ho.line else ""
                    
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
                                book = st.session_state.get("selected_book", "fanduel")
                                slate = run_async(analyze_full_slate([g], max_games=1, ledger=ledger, bookmaker=book))
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
                        tip   = g.game_time.strftime("%b %d, %I:%M %p ET")
                        book = st.session_state.get("selected_book", "fanduel")
                        ho = g.home_odds.get(book)
                        ao = g.away_odds.get(book)
                        oto = g.total_over_odds.get(book)
                        uto = g.total_under_odds.get(book)
                        hml = g.home_ml.get(book)
                        aml = g.away_ml.get(book)
                        
                        sp    = (f"Spread: {g.home_team} {ho.line:+.1f} "
                                 f"({'%+d' % ho.american_odds}) / "
                                 f"{g.away_team} {ao.line:+.1f} "
                                 f"({'%+d' % ao.american_odds})"
                                 if ho and ao else "No spread")
                        tot   = (f"O/U {oto.line} "
                                 f"(O {'%+d' % oto.american_odds} / "
                                 f"U {'%+d' % uto.american_odds})"
                                 if oto and uto else "No total")
                        ml    = (f"ML: {g.home_team} {'%+d' % hml.american_odds} / "
                                 f"{g.away_team} {'%+d' % aml.american_odds}"
                                 if hml and aml else "")
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
                                    book = st.session_state.get("selected_book", "fanduel")
                                    slate = run_async(analyze_full_slate([g], max_games=1, ledger=ledger, bookmaker=book))
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
            if not player_data or not player_data.get("name"):
                st.caption("Player data unavailable.")
                return
                
            c1, c2 = st.columns([1, 4])
            with c1:
                headshot = player_data.get("headshot", "")
                if headshot:
                    st.image(headshot, width=80)
                else:
                    st.markdown('<div style="width:80px;height:80px;border-radius:50%;background:#2d4a6e;line-height:80px;text-align:center;font-size:2rem">👤</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"**{player_data['name']}**")
                pos  = player_data.get("position", "")
                ht   = player_data.get("height", "")
                wt   = player_data.get("weight", "")
                city = player_data.get("birthPlace", "")
                yr   = player_data.get("year", "")
                
                bio_parts = [p for p in [pos, f"{ht} {wt}" if ht else "", yr, city] if p and p.strip()]
                st.caption("  ·  ".join(bio_parts))
                
                roster_stats = player_data.get("stats", {})
                if roster_stats:
                    # Filter for relevance so we don't overwhelm the card
                    key_metrics = ["PPG", "RPG", "APG", "FG%", "3P%"]
                    display_stats = {k: v for k, v in roster_stats.items() if k in key_metrics}
                    # Fallback if specific metrics aren't found
                    if not display_stats:
                         display_stats = dict(list(roster_stats.items())[:5])
                         
                    cols = st.columns(len(display_stats))
                    for col, (k, v) in zip(cols, display_stats.items()):
                        col.metric(k, v)
                        
            traits = {
                "PG": "🎯 Floor general — playmaking, A/TO ratio, pick-and-roll reads.",
                "SG": "🎯 Shooting guard — off-ball movement, catch-and-shoot, two-way.",
                "SF": "🎯 Small forward — wing defense, transition scoring, rebounding.",
                "PF": "🎯 Power forward — paint presence, screen quality, face-up game.",
                "C":  "🎯 Center — rim protection, offensive rebounding, P&R defense.",
            }
            pos_key = pos.upper()[:2] if pos else ""
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
    def show_team(team_name: str, espn_id: int, db_ranking: Optional[int], sport_key: str):
        with st.spinner(f"Loading {team_name}..."):
            summary  = fetch_team_summary(espn_id, sport_key)
            roster   = fetch_team_roster(espn_id, sport_key)
            schedule = fetch_team_schedule(espn_id, sport_key)
        best_wins, worst_losses = fetch_best_worst(schedule, espn_id)

        # ─ Header ────────────────────────────────────────────────────
        h1, h2 = st.columns([1, 4])
        with h1:
            st.image(logo_url(espn_id, sport_key), width=90)
        with h2:
            # Prefer live ESPN rank over DB ranking
            espn_rank = summary.get("rank")  # directly from ESPN API
            effective_rank = espn_rank or db_ranking
            rank_str = f' · <span style="background:{COLORS["accent"]};color:white;border-radius:20px;padding:2px 9px;font-size:.8rem;font-weight:900">#{effective_rank} AP</span>' if effective_rank else ""
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
<div style="font-size:.72rem;color:{COLORS["muted"]}">#{jersey} · {pos_tag}{ht_tag} · {year_tag}</div>
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
                            f'<span style="color:{COLORS["muted"]};min-width:82px">{date_str}</span>'
                            f'<span style="flex:1;font-weight:600">{game["name"]}</span>'
                            f'<span style="color:{COLORS["muted"]}>{score_str}</span></div>',
                            unsafe_allow_html=True,
                        )

        # ─ Facts tab ──────────────────────────────────────────────────
        with t_facts:
            db_stats = _lookup_team_stats(summary.get('name', team_name), ledger)

            loc  = summary.get("location", "")
            nick = summary.get("nickname", "")
            rec  = summary.get("record", "—")
            st.markdown(f"**{summary.get('name', team_name)}**  ·  {loc}  ·  {nick}")
            st.markdown(f"**Record:** `{rec}`")

            if not db_stats:
                st.info("Detailed scouting data not in our database for this team.")
            else:
                oe   = float(getattr(db_stats, "offensive_efficiency", 0) or 0)
                de   = float(getattr(db_stats, "defensive_efficiency", 0) or 0)
                pace = float(getattr(db_stats, "pace", 0) or 0)
                tpr  = float(getattr(db_stats, "three_point_rate", 0) or 0)
                ats  = getattr(db_stats, "ats_record", "") or ""
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
                st.markdown("**🤖 AI Scouting Overview**")
                
                # Check for cached overview, otherwise generate it
                ai_blurb = getattr(db_stats, "ai_overview", None)
                if not ai_blurb:
                    with st.spinner("Analyzing statistical profile..."):
                        stats_dict = {
                            "oe": oe, "de": de, "pace": pace, "3pr": tpr, "net": net, "record": rec
                        }
                        ai_blurb = run_async(generate_team_scouting_report(summary.get('name', team_name), stats_dict))
                        
                        # Cache it in the database for next time
                        if db_stats and hasattr(db_stats, "team_id"):
                            try:
                                ledger.db["team_stats"].update(
                                    db_stats.team_id,
                                    {"ai_overview": ai_blurb}
                                )
                            except Exception as e:
                                print(f"Warning: Could not cache AI overview: {e}")
                
                st.info(ai_blurb)

                st.markdown("**🔍 Quantitative Report**")
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

    # ── LEAGUE SELECTION ──────────────────────────────────────────────
    sport_labels = {
        "Men's College": "basketball_ncaab",
        "Women's College": "basketball_ncaaw",
        "NBA Professionals": "basketball_nba"
    }
    sel_sport_lbl = st.radio("Select League:", options=list(sport_labels.keys()), horizontal=True)
    active_sport = sport_labels[sel_sport_lbl]

    # Pull dynamic list of 362 Div 1 teams (using selected sport)
    all_teams_map = get_all_espn_teams(sport_key=active_sport)
    
    # Store all db stats for sorting lookups
    db_stats = {s.get("team_name", ""): s for s in ledger.get_all_team_stats()}
    db_ranks: dict[str, int] = {name: s.get("ranking") for name, s in db_stats.items() if s.get("ranking")}

    # Filter bar
    f1, f2, f3 = st.columns([2, 5, 2])
    search_q = f1.text_input("", placeholder="🔍 Search teams...", label_visibility="collapsed")
    
    from src.tools.espn_client import get_all_standings
    all_standings = get_all_standings()  # API does not slice standings explicitly, but team IDs are filtered above
    
    ALL_D1_CONFS = [
        "America East", "American", "ASUN", "Atlantic 10", "ACC", "Big 12", "Big East", 
        "Big Sky", "Big South", "Big Ten", "Big West", "CAA", "CUSA", "Horizon", 
        "Ivy", "MAAC", "MAC", "MEAC", "Missouri Valley", "Mountain West", "NEC", 
        "OVC", "Patriot", "SEC", "SoCon", "Southland", "SWAC", "Summit", "Sun Belt", 
        "WAC", "WCC"
    ]
    team_filter_conf = f2.multiselect("Conferences", options=["Power 5", "Mid-Major"] + ALL_D1_CONFS, default=[], label_visibility="collapsed", placeholder="Select conferences...")
    
    sort_options = ["AP Rank", "Conference Win %", "Alphabetical", "Offensive Efficiency", "Defensive Efficiency", "Pace"]
    default_idx = 1 if team_filter_conf else 0
    sort_by = f3.selectbox("Sort by", sort_options, index=default_idx, label_visibility="collapsed")

    # Sort logic
    def sort_key(item):
        name, _ = item
        s = db_stats.get(name, {})
        rank = s.get("ranking")
        standings = all_standings.get(name, {})
        
        if sort_by == "Conference Win %":
            wpct = standings.get("conf_win_pct", -1.0)
            return (0, -wpct)
        elif sort_by == "AP Rank":
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

    if team_filter_conf:
        POWER_5 = {"SEC", "ACC", "Big 12", "Big Ten", "Big East"}
        matched_confs = set(team_filter_conf)
        
        filtered_by_conf = []
        for n, i in sorted_teams:
            c = all_standings.get(n, {}).get("conference", "")
            if not c:
                continue # Skip teams outside D1 standings if hard filtering is active
                
            valid = False
            is_p5 = c in POWER_5
            
            if "Power 5" in matched_confs and is_p5:
                valid = True
            if "Mid-Major" in matched_confs and not is_p5:
                valid = True
            if c in matched_confs:
                valid = True
                
            if valid:
                filtered_by_conf.append((n, i))
        sorted_teams = filtered_by_conf

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
                    f'<div style="position:absolute;top:8px;left:8px;background:{COLORS["accent"]};'
                    f'color:white;font-size:.65rem;font-weight:900;padding:2px 7px;'
                    f'border-radius:20px">#{rank}</div>'
                ) if rank else ""

                card_html = f"""
<div style="position:relative;background:#111827;border:1px solid #1e2d45;
            border-radius:14px;padding:1rem .8rem;text-align:center;
            transition:border-color .2s;margin-bottom:.5rem">
  {rank_badge}
  <img src="{logo_url(espn_id, active_sport)}" style="width:64px;height:64px;object-fit:contain"
       onerror="this.style.display='none'">
  <div style="font-size:.82rem;font-weight:700;margin-top:.5rem;line-height:1.2">
    {team_name.split()[0]} {team_name.split()[1] if len(team_name.split()) > 1 else ''}
  </div>
</div>"""
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button("View", key=f"team_{espn_id}", use_container_width=True):
                    show_team(team_name, espn_id, rank, active_sport)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: LIVE GAME ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "live_game":
    # ── Imports ──────────────────────────────────────────────────────────────
    from src.tools.espn_client import (
        find_event_id, fetch_live_boxscore, get_espn_team_id, fetch_team_summary
    )
    from src.agents.post_mortem import generate_live_analysis, generate_scouting_report
    import asyncio
    import pandas as pd

    # ── Header ───────────────────────────────────────────────────────────────
    _hdr_l, _hdr_c, _hdr_r = st.columns([1, 5, 1])
    with _hdr_l:
        if st.button("\u2190 Back", key="live_back"):
            st.session_state.page = "home"
            st.rerun()
    with _hdr_c:
        st.markdown(
            '<div style="text-align:center;font-size:1.3rem;font-weight:800;'
            'background:linear-gradient(135deg,#f97316,#fbbf24);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent">'
            '\U0001f4e1 Live Game Analysis</div>',
            unsafe_allow_html=True
        )

    # ── Resolve bet vs. bare game info ───────────────────────────────────────
    bet_id    = st.session_state.get("live_game_bet_id")
    game_info = st.session_state.get("live_game_info")
    bet       = None

    if bet_id:
        bet_rows = list(ledger.db["bets"].rows_where("id = ?", [bet_id]))
        if bet_rows:
            bet = bet_rows[0]

    # If arrived from Today's Slate with no explicit bet, auto-detect an open bet
    if game_info and not bet:
        _gi_away = (game_info.get("away") or "").lower()
        _gi_home = (game_info.get("home") or "").lower()
        for _ob in list(ledger.db["bets"].rows_where("status IN ('pending','approved')", [])):
            if (_ob.get("away_team", "").lower() == _gi_away and
                    _ob.get("home_team", "").lower() == _gi_home):
                bet = _ob
                break

    if bet:
        away_t     = bet["away_team"]
        home_t     = bet["home_team"]
        sport      = bet.get("sport_key", "basketball_ncaab")
        _line      = bet.get("line")
        _line_part = f" ({_line:+.1f})" if _line is not None else ""
        _bet_side  = bet["side"].upper()
        market_str = f"{bet['bet_type'].upper()} {_bet_side}{_line_part}"
    elif game_info:
        away_t     = game_info.get("away", "")
        home_t     = game_info.get("home", "")
        sport      = game_info.get("sport", "basketball_ncaab")
        market_str = None
        _bet_side  = None
    else:
        st.warning("No game selected. Return home and click a bet card or use \U0001f4e1 in Today's Slate.")
        st.stop()

    matchup_str = f"{away_t} @ {home_t}"

    # ── Find ESPN event ───────────────────────────────────────────────────────
    with st.spinner(f"Looking up {matchup_str} on ESPN\u2026"):
        event_id = find_event_id(away_t, home_t, sport)

    if not event_id:
        _no_game_bet_row = (
            f'<div style="margin-top:.6rem;color:#fbbf24;font-size:.85rem">Your bet: <b>{market_str}</b></div>'
            if market_str else ""
        )
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1c1c2e,#16213e);border:1px solid #2d3748;'
            f'border-radius:12px;padding:1.5rem;text-align:center;margin:1rem 0">'
            f'<div style="font-size:1.5rem;margin-bottom:.5rem">\u23f3</div>'
            f'<div style="font-weight:700;font-size:1.1rem">{matchup_str}</div>'
            f'<div style="color:#9ca3af;margin-top:.3rem">Game not found on ESPN\u2019s current scoreboard \u2014 '
            f'it may not have started yet or isn\u2019t scheduled for today.</div>'
            f'{_no_game_bet_row}</div>',
            unsafe_allow_html=True
        )
        st.stop()

    # ── Fetch live box score ──────────────────────────────────────────────────
    with st.spinner("Fetching live data from ESPN\u2026"):
        box = fetch_live_boxscore(event_id, sport)

    if not box:
        st.error("Could not retrieve box score data from ESPN.")
        st.stop()

    game_status = box.get("status", "pre")
    hs          = box.get("home_score", 0)
    as_         = box.get("away_score", 0)
    period      = box.get("period", 0)
    clock       = box.get("clock", "")
    h_logo      = box.get("home_logo", "")
    a_logo      = box.get("away_logo", "")
    h_name      = box.get("home_team") or home_t
    a_name      = box.get("away_team") or away_t
    venue_str   = box.get("venue", "")

    if game_status == "in":
        period_label = f"H{period}" if period <= 2 else f"OT{period - 2}"
        status_label = f"LIVE \u00b7 {period_label} {clock}"
        status_color = "#ef4444"
        status_bg    = "rgba(239,68,68,.12)"
        dot_html     = (
            '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            'background:#ef4444;animation:live_pulse 1.2s infinite;'
            'vertical-align:middle;margin-right:5px"></span>'
        )
    elif game_status == "post":
        period_label = ""
        status_label = "FINAL"
        status_color = "#4ade80"
        status_bg    = "rgba(74,222,128,.1)"
        dot_html     = "\u2705 "
    else:
        period_label = ""
        status_label = "PRE-GAME"
        status_color = "#fbbf24"
        status_bg    = "rgba(251,191,36,.1)"
        dot_html     = "\U0001f550 "

    winner_away  = as_ > hs
    winner_home  = hs > as_
    away_w       = "900" if winner_away else "500"
    home_w       = "900" if winner_home else "500"
    away_op      = "1"   if (winner_away or game_status != "post") else ".5"
    home_op      = "1"   if (winner_home or game_status != "post") else ".5"

    away_ring = (
        "outline:3px solid #f97316;outline-offset:4px;border-radius:10px;"
        if (bet and _bet_side == "AWAY") else ""
    )
    home_ring = (
        "outline:3px solid #f97316;outline-offset:4px;border-radius:10px;"
        if (bet and _bet_side == "HOME") else ""
    )

    _bet_row   = (
        f'<div style="margin-top:.9rem;display:inline-block;padding:.4rem .9rem;'
        f'background:rgba(249,115,22,.12);border:1px solid rgba(249,115,22,.3);'
        f'border-radius:8px;font-size:.84rem">'
        f'\U0001f3af Your bet: <b style="color:#f97316">{market_str}</b></div>'
        if market_str else ""
    )
    _venue_row = (
        f'<div style="font-size:.73rem;color:#6b7280;margin-top:.45rem">\U0001f4cd {venue_str}</div>'
        if venue_str else ""
    )

    st.markdown(f"""
<style>
@keyframes live_pulse {{
  0%,100% {{ opacity:1; transform:scale(1); }}
  50%      {{ opacity:.4; transform:scale(1.4); }}
}}
</style>
<div style="background:linear-gradient(145deg,#0f1623,#1a2236);border:1px solid #2d3748;
            border-radius:16px;padding:2rem 1.5rem;text-align:center;margin-bottom:1.4rem;
            box-shadow:0 4px 24px rgba(0,0,0,.45)">
  <div style="display:inline-flex;align-items:center;gap:4px;padding:.3rem .85rem;
              background:{status_bg};border:1px solid {status_color}44;border-radius:99px;
              font-size:.75rem;font-weight:800;color:{status_color};letter-spacing:.1em;
              margin-bottom:1.2rem">
    {dot_html}{status_label}
  </div>
  <div style="display:flex;align-items:center;justify-content:center;gap:1.5rem;flex-wrap:wrap">
    <div style="text-align:center;flex:1;min-width:110px;opacity:{away_op}">
      <div style="font-size:.6rem;color:#6b7280;font-weight:700;letter-spacing:.15em;margin-bottom:.4rem">AWAY</div>
      <img src="{a_logo}" style="height:70px;object-fit:contain;{away_ring}" onerror="this.style.display='none'">
      <div style="font-weight:{away_w};margin-top:.45rem;font-size:.95rem;line-height:1.2">{a_name}</div>
    </div>
    <div style="text-align:center;min-width:130px">
      <div style="font-size:3.4rem;font-weight:900;letter-spacing:-3px;
                  background:linear-gradient(135deg,#f9fafb 40%,#9ca3af);
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1">
        {as_}\u00a0\u2013\u00a0{hs}
      </div>
    </div>
    <div style="text-align:center;flex:1;min-width:110px;opacity:{home_op}">
      <div style="font-size:.6rem;color:#6b7280;font-weight:700;letter-spacing:.15em;margin-bottom:.4rem">HOME</div>
      <img src="{h_logo}" style="height:70px;object-fit:contain;{home_ring}" onerror="this.style.display='none'">
      <div style="font-weight:{home_w};margin-top:.45rem;font-size:.95rem;line-height:1.2">{h_name}</div>
    </div>
  </div>
  {_bet_row}
  {_venue_row}
</div>
""", unsafe_allow_html=True)

    # ── Box Score ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:.65rem;font-weight:800;color:#6b7280;'
        'letter-spacing:.16em;margin:.5rem 0 .5rem">\U0001f4cb BOX SCORE</div>',
        unsafe_allow_html=True
    )
    teams = box.get("teams", [])
    if teams:
        tab_cols = st.columns(len(teams))
        KEY_STATS = ["MIN", "PTS", "REB", "AST", "FG", "3PT"]
        for col, team_data in zip(tab_cols, teams):
            with col:
                st.markdown(
                    f'<div style="font-weight:700;font-size:.88rem;margin-bottom:.25rem">'
                    f'{team_data["team"]}</div>',
                    unsafe_allow_html=True
                )
                players  = team_data.get("players", [])
                if not players:
                    st.caption("No player data yet.")
                    continue
                labels   = players[0].get("labels", [])
                show_idx = [i for i, lbl in enumerate(labels) if lbl in KEY_STATS]
                show_lbl = [labels[i] for i in show_idx]
                rows = []
                for p in players[:10]:
                    stats = p.get("stats", [])
                    row   = {"Player": p["name"]}
                    for i, lbl in zip(show_idx, show_lbl):
                        row[lbl] = stats[i] if i < len(stats) else "-"
                    rows.append(row)
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows),
                        hide_index=True,
                        use_container_width=True,
                        height=min(380, 38 + 35 * len(rows)),
                    )
    elif game_status == "pre":
        st.info("Box score will appear once the game tips off.")
    else:
        st.caption("Box score data not available.")

    # ── AI Scouting Report ────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:.65rem;font-weight:800;color:#6b7280;'
        'letter-spacing:.16em;margin:1.1rem 0 .5rem">\U0001f50d AI SCOUTING REPORT</div>',
        unsafe_allow_html=True
    )
    scout_key   = f"scout_{event_id}"
    scout_text  = st.session_state.live_analysis_cache.get(scout_key)

    if not scout_text:
        def _build_team_ctx(tname: str) -> str:
            _lines = [f"Team: {tname}"]
            _eid = get_espn_team_id(tname, sport)
            if _eid:
                _sm = fetch_team_summary(_eid, sport)
                if _sm:
                    _lines.append(
                        f"Record: {_sm.get('record','N/A')} "
                        f"(Home: {_sm.get('home_record','?')}, Road: {_sm.get('road_record','?')})"
                    )
                    if _sm.get("rank"):
                        _lines.append(f"AP Rank: #{_sm['rank']}")
                    if _sm.get("standing"):
                        _lines.append(f"Conference: {_sm['standing']}")
            _all = ledger.get_all_team_stats()
            _ts  = next((r for r in _all if r.get("team_name","").lower() == tname.lower()), None)
            if _ts:
                _lines.append(
                    f"AdjO: {_ts.get('adj_o','N/A')}, AdjD: {_ts.get('adj_d','N/A')}, "
                    f"Pace: {_ts.get('pace','N/A')}, 3PT%: {_ts.get('three_pt_rate','N/A')}"
                )
            return "\n".join(_lines)

        with st.spinner("Building scouting report\u2026"):
            try:
                _ctx = _build_team_ctx(away_t) + "\n\n" + _build_team_ctx(home_t)
                scout_text = asyncio.run(
                    generate_scouting_report(
                        away_team=a_name or away_t,
                        home_team=h_name or home_t,
                        team_context=_ctx,
                    )
                )
                st.session_state.live_analysis_cache[scout_key] = scout_text
            except Exception as _se:
                scout_text = f"Scouting report unavailable: {_se}"

    st.markdown(
        f'<div style="background:linear-gradient(145deg,#0a1520,#0f1b2d);'
        f'border:1px solid #1e3a5f;border-left:3px solid #38bdf8;'
        f'border-radius:10px;padding:1.2rem 1.4rem;line-height:1.7;font-size:.9rem">'
        f'{scout_text.replace(chr(10), "<br>")}</div>',
        unsafe_allow_html=True
    )

    # ── AI Live Analysis ──────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:.65rem;font-weight:800;color:#6b7280;'
        'letter-spacing:.16em;margin:1.1rem 0 .5rem">\U0001f916 AI LIVE ANALYSIS</div>',
        unsafe_allow_html=True
    )

    live_key      = f"live_{event_id}_{game_status}_{hs}_{as_}"
    analysis_text = st.session_state.live_analysis_cache.get(live_key)

    if not analysis_text and bet:
        _score_ctx = f"Current score: {a_name} {as_}, {h_name} {hs}"
        if game_status == "in":
            _score_ctx += f" ({period_label}, {clock} remaining)"
        elif game_status == "post":
            _score_ctx += " \u2014 FINAL"
        _top = []
        for _td in teams:
            _pts_i = None
            if _td["players"]:
                _labs = _td["players"][0].get("labels", [])
                _pts_i = _labs.index("PTS") if "PTS" in _labs else None
            if _pts_i is not None:
                for _p in _td["players"][:3]:
                    _pts = _p["stats"][_pts_i] if _pts_i < len(_p["stats"]) else "?"
                    _top.append(f"{_p['name']} ({_td['team']}): {_pts} pts")
        if _top:
            _score_ctx += "\nTop scorers: " + ", ".join(_top[:6])

        _explicit = market_str
        if _bet_side == "HOME":
            _explicit = f"{market_str} (betting on {h_name} to win/cover)"
        elif _bet_side == "AWAY":
            _explicit = f"{market_str} (betting on {a_name} to win/cover)"

        with st.spinner("Generating AI analysis\u2026"):
            try:
                analysis_text = asyncio.run(
                    generate_live_analysis(
                        matchup=f"{a_name} (AWAY) @ {h_name} (HOME)",
                        market=_explicit,
                        rationale=bet.get("summary", "No rationale recorded."),
                        live_context=_score_ctx,
                    )
                )
                st.session_state.live_analysis_cache[live_key] = analysis_text
            except Exception as _ae:
                analysis_text = f"AI analysis unavailable: {_ae}"

    if analysis_text:
        st.markdown(
            f'<div style="background:linear-gradient(145deg,#14102a,#1a1433);'
            f'border:1px solid #2d1f5e;border-left:3px solid #a855f7;'
            f'border-radius:10px;padding:1.2rem 1.4rem;line-height:1.7;font-size:.9rem">'
            f'{analysis_text.replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="background:#111827;border:1px solid #2d3748;border-radius:10px;'
            'padding:1rem;color:#6b7280;font-size:.88rem;text-align:center">'
            '\U0001f440 Live analysis available when viewing from an approved bet</div>',
            unsafe_allow_html=True
        )

    # ── Refresh ───────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _r1, _r2 = st.columns([5, 1])
    with _r2:
        if st.button("\U0001f504 Refresh", key="live_refresh", use_container_width=True):
            _kill = [k for k in st.session_state.live_analysis_cache
                     if event_id in k]
            for _k in _kill:
                del st.session_state.live_analysis_cache[_k]
            st.rerun()



# ══════════════════════════════════════════════════════════════════════════════
# PAGE: TOURNAMENT PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "tourney":
    from src.tools.math_model import project_matchup
    from src.agents.post_mortem import generate_scouting_report
    import asyncio
    
    st.markdown('<div class="page-title">🏆 March Madness Predictor</div>', unsafe_allow_html=True)
    st.markdown('''
    <div style="font-size:0.9rem; color:#9ca3af; margin-bottom: 2rem;">
        Simulate any head-to-head matchup using KenPom-style efficiency metrics (AdjO, AdjD, Pace).
        Perfect for bracket research and finding +EV upsets.
    </div>
    ''', unsafe_allow_html=True)
    
    # 1. Fetch available teams
    all_team_stats = ledger.get_all_team_stats()
    if not all_team_stats:
        st.warning("No team stats available. Please run data ingest first.")
        st.stop()
        
    team_names = sorted([t["team_name"] for t in all_team_stats])
    
    # Session state for selections
    if "tourney_away" not in st.session_state:
        st.session_state.tourney_away = team_names[0] if team_names else ""
    if "tourney_home" not in st.session_state:
        st.session_state.tourney_home = team_names[1] if len(team_names) > 1 else ""
        
    # Team Selector UI
    st.markdown("### Matchup Selection")
    col1, col2, col3 = st.columns([4, 1, 4])
    with col1:
        away_choice = st.selectbox("Away / Lower Seed", options=team_names, index=team_names.index(st.session_state.tourney_away) if st.session_state.tourney_away in team_names else 0)
    with col2:
        st.markdown('<div style="text-align:center; font-size:1.5rem; font-weight:800; margin-top:1.5rem; color:#6b7280;">@</div>', unsafe_allow_html=True)
    with col3:
        home_choice = st.selectbox("Home / Higher Seed", options=team_names, index=team_names.index(st.session_state.tourney_home) if st.session_state.tourney_home in team_names else 0)
    
    is_neutral = st.checkbox("Neutral Site Game (March Madness is always neutral site)", value=True)
    
    st.session_state.tourney_away = away_choice
    st.session_state.tourney_home = home_choice
    
    if away_choice == home_choice:
        st.error("Please select two different teams.")
        st.stop()
        
    # Get stats dictionary for the choices
    away_stats = next((t for t in all_team_stats if t["team_name"] == away_choice), {})
    home_stats = next((t for t in all_team_stats if t["team_name"] == home_choice), {})
    
    # 2. Mathematical Projection
    st.markdown("---")
    res = project_matchup(away_stats, home_stats, is_neutral_site=is_neutral)
    
    # Display the projection
    st.markdown("### 📊 Mathematical Projection")
    
    # Hero Result Card
    home_favored = res["projected_margin"] > 0
    favored_team = home_choice if home_favored else away_choice
    underdog = away_choice if home_favored else home_choice
    margin = abs(res["projected_margin"])
    fav_win_prob = res["home_win_prob"] if home_favored else res["away_win_prob"]
    
    st.markdown(f'''
    <div class="glass-card" style="padding: 2rem; text-align: center; margin-bottom: 2rem; border-left: 4px solid #f97316;">
        <div style="font-size: 1.1rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem;">Predicted Winner</div>
        <div style="font-size: 2.5rem; font-weight: 900; background: linear-gradient(135deg, #f9fafb, #9ca3af); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            {favored_team} by {margin:.1f}
        </div>
        <div style="font-size: 1rem; color: #fbbf24; margin-top: 0.5rem; font-weight: 600;">
            {favored_team} {fav_win_prob*100:.1f}% Win Probability
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Detail columns
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Projected Score**<br>{away_choice}: {res['away_score']:.1f}<br>{home_choice}: {res['home_score']:.1f}", unsafe_allow_html=True)
    with c2:
        st.markdown(f"**Efficiency Profile**<br>{away_choice} AdjO/AdjD: {away_stats.get('adj_o', 'N/A')} / {away_stats.get('adj_d', 'N/A')}<br>{home_choice} AdjO/AdjD: {home_stats.get('adj_o', 'N/A')} / {home_stats.get('adj_d', 'N/A')}", unsafe_allow_html=True)
    with c3:
        st.markdown(f"**Pace Details**<br>Expected Possessions: {res['expected_possessions']:.1f}<br>{away_choice} Pace: {away_stats.get('pace', 'N/A')}<br>{home_choice} Pace: {home_stats.get('pace', 'N/A')}", unsafe_allow_html=True)
        
    # 3. AI Scouting Report
    st.markdown("---")
    st.markdown("### 🔍 AI Deep Dive Scouting")
    
    scout_cache_key = f"tourney_scout_{away_choice}_{home_choice}"
    if scout_cache_key in st.session_state.live_analysis_cache:
        st.markdown(st.session_state.live_analysis_cache[scout_cache_key], unsafe_allow_html=True)
        if st.button("Regenerate Scouting Report"):
            del st.session_state.live_analysis_cache[scout_cache_key]
            st.rerun()
    else:
        st.markdown("Get an AI summary on how these teams match up, their strengths and weaknesses, and X-factors.")
        if st.button("Generate AI Scouting Report", type="primary"):
            def _build_ctx(tname: str, tstats: dict) -> str:
                return (
                    f"Team: {tname}\n"
                    f"AdjO: {tstats.get('adj_o')}, AdjD: {tstats.get('adj_d')}, Pace: {tstats.get('pace')}\n"
                    f"3PTRate: {tstats.get('three_pt_rate')}, FTRate: {tstats.get('ft_rate')}"
                )
                
            ctx = _build_ctx(away_choice, away_stats) + "\n\n" + _build_ctx(home_choice, home_stats)
            
            with st.spinner("Generating scouting report..."):
                try:
                    scout_text = asyncio.run(
                        generate_scouting_report(
                            away_team=away_choice,
                            home_team=home_choice,
                            team_context=ctx
                        )
                    )
                    
                    styled_text = f'''
                    <div style="background:linear-gradient(145deg,#0a1520,#0f1b2d);
                                border:1px solid #1e3a5f;border-left:3px solid #38bdf8;
                                border-radius:10px;padding:1.4rem;line-height:1.7;font-size:0.95rem; margin-top:1rem;">
                        {scout_text.replace(chr(10), "<br>")}
                    </div>
                    '''
                    st.session_state.live_analysis_cache[scout_cache_key] = styled_text
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate scouting report: {e}")
                    

