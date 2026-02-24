"""
Hoops Edge — Premium Streamlit Dashboard
Run with: streamlit run src/ui/app.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import asyncio
import streamlit as st
from datetime import datetime

from src.db.storage import BetLedger
from src.tools.odds_client import get_live_games
from src.agents.ev_calculator import analyze_full_slate
from src.tools.espn_client import (
    fetch_team_summary, fetch_team_roster, fetch_team_schedule,
    fetch_boxscore, fetch_player_stats, logo_url, TEAM_ESPN_IDS
)

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
#MainMenu, footer {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ visibility: hidden; }}

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
    wins   = sum(1 for b in settled if b["result"] == "win")
    losses = sum(1 for b in settled if b["result"] == "loss")
    total_pl = sum(b["profit_loss"] for b in settled if b["profit_loss"] is not None)
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
    ev_bets = [b for b in pending_bets if b["status"] == "approved"]

    st.markdown(f"""
<div class="hero">
  <h1>🏀 Hoops Edge</h1>
  <p>AI-Powered College Basketball Edge Detection</p>
  <p style="color:#4b5563;font-size:0.85rem;margin-top:0.8rem">{today}</p>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class="stat-tile">
          <div class="val">{bankroll['balance_units']:.0f}u</div>
          <div class="lbl">Bankroll</div></div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="stat-tile">
          <div class="val">{wins}–{losses}</div>
          <div class="lbl">Record</div></div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="stat-tile">
          <div class="val">{len(pending_bets)}</div>
          <div class="lbl">Pending Bets</div></div>""", unsafe_allow_html=True)
    with c4:
        pl_sign = "+" if total_pl >= 0 else ""
        st.markdown(f"""<div class="stat-tile">
          <div class="val" style="color:{'#22c55e' if total_pl >= 0 else '#ef4444'}">{pl_sign}{total_pl:.1f}u</div>
          <div class="lbl">All-time P/L</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="page-title">Quick Actions</div>', unsafe_allow_html=True)

    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        st.markdown(f"""<div class="glass-card accent">
          <div style="font-size:1.8rem">📋</div>
          <div style="font-weight:700;margin:.4rem 0 .2rem">Today's Slate</div>
          <div style="font-size:.85rem;color:{COLORS['text2']}">Load live FanDuel lines and pick your games</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Open Slate →", key="home_slate"):
            st.session_state.page = "slate"
            st.rerun()

    with qa2:
        st.markdown(f"""<div class="glass-card green">
          <div style="font-size:1.8rem">⏳</div>
          <div style="font-weight:700;margin:.4rem 0 .2rem">Pending Bets</div>
          <div style="font-size:.85rem;color:{COLORS['text2']}">{len(pending_bets)} bet(s) awaiting your action</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Review Bets →", key="home_pending"):
            st.session_state.page = "pending"
            st.rerun()

    with qa3:
        st.markdown(f"""<div class="glass-card gold">
          <div style="font-size:1.8rem">🔍</div>
          <div style="font-weight:700;margin:.4rem 0 .2rem">Game Search</div>
          <div style="font-size:.85rem;color:{COLORS['text2']}">Look up odds for any team or conference</div>
        </div>""", unsafe_allow_html=True)
        if st.button("Search Games →", key="home_search"):
            st.session_state.page = "search"
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

        # ── Single-click checkboxes (no double-click required) ─────────────────────────
        # Persist checked state in session
        if "game_checks" not in st.session_state:
            st.session_state.game_checks = {}

        # Select All / Clear All row
        sa_col, ca_col, _ = st.columns([1, 1, 6])
        if sa_col.button("☑ Select All"):
            for g in sorted_games:
                st.session_state.game_checks[g.game_id] = True
            st.rerun()
        if ca_col.button("☐ Clear All"):
            st.session_state.game_checks = {}
            st.rerun()

        for g in sorted_games:
            away_r = f"#{g.away_stats.ranking} " if (g.away_stats and g.away_stats.ranking) else ""
            home_r = f"#{g.home_stats.ranking} " if (g.home_stats and g.home_stats.ranking) else ""
            away_rec = f" ({g.away_stats.record})" if g.away_stats else ""
            home_rec = f" ({g.home_stats.record})" if g.home_stats else ""
            tip = g.game_time.strftime("%I:%M %p ET")
            star = "⭐ " if (g.home_stats or g.away_stats) else " "
            game_label = (
                f"{star}{away_r}{g.away_team}{away_rec}   @   "
                f"{home_r}{g.home_team}{home_rec}  ·  {tip}"
            )
            checked = st.session_state.game_checks.get(g.game_id, False)
            new_val = st.checkbox(game_label, value=checked, key=f"chk_{g.game_id}")
            if new_val != checked:
                st.session_state.game_checks[g.game_id] = new_val

        selected_ids = [gid for gid, v in st.session_state.game_checks.items() if v]
        n_sel = len(selected_ids)

        st.markdown("")
        if n_sel > 0:
            if st.button(
                f"▶ Analyze {n_sel} Selected Game{'s' if n_sel != 1 else ''}",
                type="primary",
            ):
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
        else:
            st.info("↑ Check the games you want to analyze")
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
                        if p_col.button(
                            "📌 Place",
                            key=f"place_{bet_key}",
                            type="primary",
                            use_container_width=True,
                        ):
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

                with st.expander("🧠 Reasoning"):
                    for i, step in enumerate(rec.ev_analysis.reasoning_steps, 1):
                        st.markdown(f"**{i}.** {step}")
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
    st.markdown('<div class="page-title">⏳ Pending Bets</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Manage and settle your active positions</div>', unsafe_allow_html=True)

    pending = list(ledger.db["bets"].rows_where("status IN ('pending','approved')", []))

    # ── Danger zone: clear all ────────────────────────────────────────────────
    if pending:
        with st.expander("⚠️ Danger zone"):
            st.warning("This will permanently delete ALL pending and approved bets.")
            if st.button("🗑 Clear All Pending Bets", type="primary"):
                ledger.db.execute("DELETE FROM bets WHERE status IN ('pending','approved')")
                ledger.db.conn.commit()
                st.success("All pending bets cleared.")
                st.rerun()

    if not pending:
        st.markdown(f"""<div class="glass-card" style="text-align:center;padding:2.5rem">
          <div style="font-size:3rem">✅</div>
          <div style="font-weight:700;margin:.4rem 0 .2rem">All clear</div>
          <div style="color:{COLORS['muted']}">No pending bets. Head to <b>Today's Slate</b> to generate picks.</div>
        </div>""", unsafe_allow_html=True)
    else:
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


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "history":
    st.markdown('<div class="page-title">📈 Performance</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Your betting record and bankroll history</div>', unsafe_allow_html=True)

    bankroll = ledger.get_bankroll()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Balance", f"{bankroll['balance_units']:.1f}u")
    c2.metric("Unit Size", f"${bankroll['unit_dollar_value']:.2f}")
    c3.metric("Record", f"{wins}W – {losses}L")
    c4.metric("All-time P/L", f"{total_pl:+.2f}u",
              delta_color="normal" if total_pl >= 0 else "inverse")

    st.markdown("")
    st.markdown('<div class="page-title" style="font-size:1.1rem">📜 Settled Bets</div>', unsafe_allow_html=True)

    if not settled:
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
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: GAME SEARCH
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "search":
    st.markdown('<div class="page-title">🔍 Game Search</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Type a team, conference, or keyword — get live FanDuel odds instantly</div>', unsafe_allow_html=True)

    for msg in st.session_state.search_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

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
                        card = f"""<div class="glass-card accent" style="margin:.5rem 0">
<div style="font-weight:800;font-size:1rem">{g.away_team} <span style="color:{COLORS['muted']}">@</span> {g.home_team}
<span style="font-size:.75rem;color:{COLORS['muted']};font-weight:400;margin-left:8px">{tip}{conf}</span></div>
<div style="font-size:.85rem;color:{COLORS['text2']};margin-top:.4rem">📊 {sp}</div>
<div style="font-size:.85rem;color:{COLORS['text2']}">🎯 {tot}</div>
{"<div style='font-size:.85rem;color:"+COLORS['text2']+"'>💰 "+ml+"</div>" if ml else ""}
</div>"""
                        st.markdown(card, unsafe_allow_html=True)
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

    # ─ Dialogs ────────────────────────────────────────────────────────────────
    @st.dialog("📊 Player Stats", width="large")
    def show_player(player_id: str, player_name: str):
        with st.spinner(f"Loading {player_name}..."):
            info = fetch_player_stats(player_id)
        if not info:
            st.warning("Could not load player data.")
            return
        c1, c2 = st.columns([1, 3])
        with c1:
            if info.get("headshot"):
                st.image(info["headshot"], width=120)
        with c2:
            st.markdown(f"### {info['name']}")
            st.markdown(f"""
| | |
|---|---|
| **Position** | {info.get('position','—')} |
| **Height** | {info.get('height','—')} |
| **Weight** | {info.get('weight','—')} lbs |
| **From** | {info.get('birthPlace') or info.get('college','—')} |
""")
        # Scouting report based on position
        pos = info.get("position", "").upper()
        traits = {
            "PG": "🎯 Floor general. Look for playmaking, assist-to-turnover ratio, and pick-and-roll reads.",
            "SG": "🎯 Shooting guard. Evaluate off-ball movement, catch-and-shoot efficiency, and two-way versatility.",
            "SF": "🎯 Small forward. Assess wing defense, transition scoring, and positional rebounding.",
            "PF": "🎯 Power forward. Focus on paint presence, screen quality, and mid-range/face-up ability.",
            "C":  "🎯 Center. Evaluate rim protection, offensive rebounding, and pick-and-roll defense.",
        }
        st.markdown("---")
        st.markdown(f"**Scouting Notes:** {traits.get(pos, 'Versatile player. Evaluate holistically across all facets.')}")

    @st.dialog("📊 Box Score", width="large")
    def show_boxscore(event_id: str, game_name: str):
        st.markdown(f"### {game_name}")
        with st.spinner("Loading box score..."):
            bs = fetch_boxscore(event_id)
        if not bs or not bs.get("teams"):
            st.warning("Box score not available for this game.")
            return
        if bs.get("result"):
            st.markdown(f"**Final:** {bs['result']}")
        for team in bs["teams"]:
            st.markdown(f"#### {team['team']}")
            players = team.get("players", [])
            if not players:
                st.caption("No player data available.")
                continue
            labels = players[0].get("labels", [])
            rows = []
            for p in players:
                row = {"Player": p["name"], "Pos": p.get("position", "")}
                for lbl, val in zip(labels, p.get("stats", [])):
                    row[lbl] = val
                rows.append(row)
            st.dataframe(rows, use_container_width=True, hide_index=True)

    @st.dialog("🏀 Team Details", width="large")
    def show_team(team_name: str, espn_id: int, db_ranking: int | None):
        with st.spinner(f"Loading {team_name}..."):
            summary  = fetch_team_summary(espn_id)
            roster   = fetch_team_roster(espn_id)
            schedule = fetch_team_schedule(espn_id)

        # Header
        h1, h2 = st.columns([1, 4])
        with h1:
            st.image(logo_url(espn_id), width=90)
        with h2:
            rank_str = f" · **#{db_ranking} AP**" if db_ranking else ""
            st.markdown(f"## {summary.get('name', team_name)}{rank_str}")
            rec = summary.get("record", "")
            conf = ""
            # Try DB for conference
            all_stats = ledger.get_all_team_stats()
            for s in all_stats:
                if s.get("team_name", "").lower() in team_name.lower() or team_name.lower() in s.get("team_name", "").lower():
                    conf = s.get("conference", "")
                    break
            st.markdown(f"`{rec}`  {conf}")

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
                        pos_tag = p.get("position", "")
                        year_tag = p.get("year", "")
                        jersey  = p.get("jersey", "")
                        card_html = f"""
<div style="background:#1a2236;border:1px solid #1e2d45;border-radius:12px;
            padding:.8rem;margin-bottom:.5rem;text-align:center;cursor:pointer">
{f'<img src="{headshot}" style="width:60px;height:60px;border-radius:50%;object-fit:cover;margin-bottom:.4rem">' if headshot else '<div style="width:60px;height:60px;border-radius:50%;background:#2d4a6e;margin:0 auto .4rem;line-height:60px;font-size:1.2rem">👤</div>'}
<div style="font-weight:700;font-size:.9rem">{p['name']}</div>
<div style="font-size:.75rem;color:#6b7280">#{jersey} · {pos_tag} · {year_tag}</div>
</div>"""
                        st.markdown(card_html, unsafe_allow_html=True)
                        if st.button("Stats & Report", key=f"player_{espn_id}_{p['id']}",
                                     use_container_width=True):
                            show_player(str(p["id"]), p["name"])

        # ─ Schedule tab ───────────────────────────────────────────────
        with t_sched:
            if not schedule:
                st.info("Schedule not available.")
            else:
                for game in schedule:
                    date_str = game["date"][:10] if game["date"] else ""
                    completed = game.get("completed", False)
                    status    = game.get("status", "")
                    if completed and game.get("home_score") and game.get("away_score"):
                        score_str = f"**{game['away_score']} – {game['home_score']}**"
                    elif not completed:
                        score_str = f"*{status}*"
                    else:
                        score_str = status

                    sc1, sc2, sc3 = st.columns([2, 3, 2])
                    sc1.caption(date_str)
                    sc2.markdown(f"{game['name']}    {score_str}")
                    if completed:
                        if sc3.button("📊 Box Score", key=f"bs_{game['event_id']}",
                                       use_container_width=True):
                            show_boxscore(str(game["event_id"]), game["name"])
                    st.markdown("---")

        # ─ Facts tab ──────────────────────────────────────────────────
        with t_facts:
            db_stats = None
            for s in ledger.get_all_team_stats():
                if s.get("team_name", "").lower() in team_name.lower() or team_name.lower() in s.get("team_name", "").lower():
                    db_stats = s
                    break

            loc  = summary.get("location", "")
            nick = summary.get("nickname", "")
            st.markdown(f"**Location:** {loc}")
            st.markdown(f"**Nickname:** {nick}")
            st.markdown(f"**Record:** {summary.get('record', '—')}")
            if db_stats:
                st.markdown("---")
                st.markdown("**Performance Metrics (from DB)**")
                fm1, fm2, fm3, fm4 = st.columns(4)
                fm1.metric("Off. Efficiency", f"{db_stats.get('offensive_efficiency', 0):.1f}")
                fm2.metric("Def. Efficiency", f"{db_stats.get('defensive_efficiency', 0):.1f}")
                fm3.metric("Pace",            f"{db_stats.get('pace', 0):.1f}")
                fm4.metric("3PT Rate",        f"{db_stats.get('three_point_rate', 0):.1%}")
                if db_stats.get('ats_record'):
                    st.markdown(f"**ATS Record:** {db_stats['ats_record']}")

    # ─ Teams Grid page body ──────────────────────────────────────────────
    st.markdown('<div class="page-title">🏀 Teams Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Click any team to view roster, schedule, and facts powered by ESPN</div>', unsafe_allow_html=True)

    # Build ranking map from live AP poll + DB
    db_ranks: dict[str, int] = {}
    for s in ledger.get_all_team_stats():
        if s.get("ranking") and s.get("team_name"):
            db_ranks[s["team_name"]] = s["ranking"]

    # Sort: ranked first (by rank), then alphabetical
    def sort_key(item):
        name, _ = item
        rank = db_ranks.get(name)
        return (0, rank) if rank else (1, name)

    sorted_teams = sorted(TEAM_ESPN_IDS.items(), key=sort_key)

    # Filter bar
    search_q = st.text_input("", placeholder="🔍 Search teams...", label_visibility="collapsed")
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
