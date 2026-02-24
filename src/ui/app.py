"""
Hoops Edge — Streamlit Dashboard
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

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hoops Edge",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Dark background */
    .stApp { background-color: #0f1117; color: #e0e0e0; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1a1d27; }

    /* Bet cards */
    .bet-card {
        background: linear-gradient(135deg, #1e2235, #252942);
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
        border-left: 4px solid #4CAF50;
    }
    .bet-card.yellow { border-left-color: #FFC107; }
    .bet-card.red    { border-left-color: #F44336; }

    /* EV badge */
    .ev-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
    }
    .ev-green { background: #1b4d2e; color: #4CAF50; }
    .ev-yellow { background: #4d3800; color: #FFC107; }

    /* Remove default padding on metric */
    [data-testid="metric-container"] { background: #1e2235; border-radius: 10px; padding: 0.5rem 1rem; }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1e2235;
        border-radius: 8px 8px 0 0;
        color: #aaa;
        padding: 0.5rem 1.2rem;
    }
    .stTabs [aria-selected="true"] { background-color: #2d3250; color: #fff; }

    h1, h2, h3 { color: #ffffff; }
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_ledger():
    return BetLedger()


def run_async(coro):
    """Run an async coroutine from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def ev_color(ev: float) -> str:
    if ev >= 0.05:
        return "green"
    if ev >= 0.035:
        return "yellow"
    return "red"


def ev_badge(ev: float) -> str:
    pct = f"{ev:+.1%}"
    if ev >= 0.05:
        return f'<span class="ev-badge ev-green">{pct}</span>'
    return f'<span class="ev-badge ev-yellow">{pct}</span>'


# ── Sidebar ────────────────────────────────────────────────────────────────────
ledger = get_ledger()

with st.sidebar:
    st.markdown("## 🏀 Hoops Edge")
    st.markdown("*CBB +EV Betting Agent*")
    st.divider()

    # Bankroll summary
    bankroll = ledger.get_bankroll()
    settled = list(ledger.db["bets"].rows_where("status = ?", ["settled"]))
    wins = sum(1 for b in settled if b["result"] == "win")
    losses = sum(1 for b in settled if b["result"] == "loss")
    total_pl = sum(b["profit_loss"] for b in settled if b["profit_loss"] is not None)

    st.metric("💰 Bankroll", f"{bankroll['balance_units']:.1f}u",
              delta=f"{total_pl:+.2f}u all-time" if settled else None)
    st.metric("Record", f"{wins}W – {losses}L")
    st.divider()

    # Run controls
    st.markdown("### Slate Controls")
    load_btn = st.button("📥 Load Today's Games", use_container_width=True,
                         help="Fetch full FanDuel NCAAB slate (1 API call, no LLM)")
    dry_run = st.checkbox("Dry run (don't save to DB)", value=False)
    st.divider()

    st.markdown(f"<small>Last updated: {datetime.now().strftime('%b %d %H:%M')}</small>",
                unsafe_allow_html=True)


# ── Main area ──────────────────────────────────────────────────────────────────
st.markdown("# 🏀 Hoops Edge Dashboard")
st.markdown(f"**{datetime.now().strftime('%A, %B %d %Y')}** &nbsp;·&nbsp; FanDuel NCAAB",
            unsafe_allow_html=True)
st.divider()

tab_picks, tab_pending, tab_history, tab_search = st.tabs([
    "📋 Today's Picks", "⏳ Pending Bets", "📊 History & Bankroll", "🔍 Game Search"
])


# ── TAB 1: Today's Picks ───────────────────────────────────────────────────────
with tab_picks:
    # Initialise session state
    for key, val in [("slate", None), ("slate_error", None),
                     ("all_games", None), ("selected_ids", [])]:
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Step 1: Load games ────────────────────────────────────────────────────
    if load_btn:
        with st.spinner("📥 Fetching live FanDuel NCAAB slate..."):
            try:
                games = get_live_games(ledger)
                st.session_state.all_games = games
                st.session_state.slate = None          # reset previous analysis
                st.session_state.selected_ids = []     # reset selections
                st.toast(f"Loaded {len(games)} games from FanDuel!", icon="✅")
            except Exception as e:
                st.error(f"**Error loading games:** {e}")

    # ── Step 2: Game selection ────────────────────────────────────────────────
    if st.session_state.all_games:
        all_games = st.session_state.all_games

        # ── Helpers ───────────────────────────────────────────────────────────
        POWER_CONFERENCES = {"Big East", "Big 12", "SEC", "ACC", "Big Ten", "Pac-12"}

        def _win_pct(record: str) -> float:
            """Parse 'W-L' into a win percentage float."""
            try:
                w, l = record.split("-")
                total = int(w) + int(l)
                return int(w) / total if total else 0.0
            except Exception:
                return 0.0

        def _rank_tag(stats) -> str:
            """Return '#N ' prefix if ranked, '' otherwise."""
            if stats and stats.ranking:
                return f"#{stats.ranking} "
            return ""

        def _record_tag(stats) -> str:
            """Return '(W-L)' if stats exist, '' otherwise."""
            return f"({stats.record})" if stats else ""

        def _intrigue_score(g) -> float:
            """
            Higher = more intriguing matchup to bet on.
            Factors (descending priority):
              1. Both teams ranked           → +10 each
              2. One team ranked             → +10
              3. Both teams have good record → +5 each if win% > .650
              4. Power conference game       → +3
              5. Has stats (quality info)    → +2 per team
            """
            score = 0.0
            for stats in [g.home_stats, g.away_stats]:
                if stats:
                    if stats.ranking:
                        score += 10
                    if _win_pct(stats.record) > 0.65:
                        score += 5
                    if stats.conference in POWER_CONFERENCES:
                        score += 3
                    score += 2  # has stats at all
            return score

        # Sort games by intrigue before building labels
        sorted_games = sorted(all_games, key=_intrigue_score, reverse=True)

        def _game_label(g) -> str:
            away_rank = _rank_tag(g.away_stats)
            home_rank = _rank_tag(g.home_stats)
            away_rec  = _record_tag(g.away_stats)
            home_rec  = _record_tag(g.home_stats)
            tip       = g.game_time.strftime("%I:%M %p ET")
            data_star = "⭐ " if (g.home_stats or g.away_stats) else ""
            return (
                f"{data_star}"
                f"{away_rank}{g.away_team} {away_rec} "
                f"@ {home_rank}{g.home_team} {home_rec}  "
                f"· {tip}"
            )

        game_labels  = {g.game_id: _game_label(g) for g in sorted_games}
        id_to_game   = {g.game_id: g for g in all_games}
        ranked_count = sum(1 for g in all_games
                           if (g.home_stats and g.home_stats.ranking)
                           or (g.away_stats and g.away_stats.ranking))

        st.markdown(f"### 📋 Select Games to Analyze "
                    f"({len(all_games)} available · {ranked_count} ranked matchups)")
        st.caption(
            "⭐ = team stats available  ·  "
            "#N = AP ranking  ·  "
            "sorted by matchup intrigue (ranked games first)"
        )

        selected_ids = st.multiselect(
            "Pick the games you want to bet on:",
            options=list(game_labels.keys()),
            format_func=lambda gid: game_labels[gid],
            default=[sid for sid in st.session_state.selected_ids
                     if sid in game_labels],  # guard stale IDs
            placeholder="Choose one or more games...",
        )
        st.session_state.selected_ids = selected_ids

        analyze_btn = st.button(
            f"▶ Analyze {len(selected_ids)} Selected Game{'s' if len(selected_ids) != 1 else ''}",
            type="primary",
            disabled=(len(selected_ids) == 0),
        )

        if analyze_btn and selected_ids:
            chosen_games = [id_to_game[gid] for gid in selected_ids]
            st.session_state.slate = None
            st.session_state.slate_error = None
            with st.spinner(f"🤖 Running EV analysis on {len(chosen_games)} game(s)..."):
                try:
                    from src.agents.ev_calculator import analyze_full_slate
                    slate = run_async(analyze_full_slate(chosen_games,
                                                        max_games=len(chosen_games)))
                    st.session_state.slate = slate
                except Exception as e:
                    st.session_state.slate_error = str(e)

        st.divider()



    elif not load_btn:
        st.info("👈 Click **Load Today's Games** in the sidebar to fetch this evening's FanDuel slate.")


    else:
        slate = st.session_state.slate
        recommended = [b for b in slate.bets if b.is_recommended]

        col1, col2, col3 = st.columns(3)
        col1.metric("Games Analyzed", slate.games_analyzed)
        col2.metric("+EV Bets Found", len(recommended))
        col3.metric("Units at Risk", f"{slate.total_units_at_risk:.2f}u")
        st.markdown("")

        if not recommended:
            st.warning("No +EV bets passed the quality threshold today. Sit on your hands. 🙌")
        else:
            for rec in recommended:
                color = ev_color(rec.ev_analysis.expected_value)
                line_str = f" {rec.line:+.1f}" if rec.line else ""
                tip = rec.game_time.strftime("%I:%M %p ET") if rec.game_time else ""

                with st.container():
                    st.markdown(f"""
<div class="bet-card {color}">
<h4 style="margin:0 0 0.4rem 0">
  {rec.away_team} <span style="color:#888">@</span> {rec.home_team}
  <span style="font-size:0.75rem; color:#888; font-weight:400; margin-left:8px">{tip}</span>
</h4>
<p style="margin:0 0 0.6rem 0; font-size:0.95rem">
  <b>{rec.bet_type.value.upper()}</b> &nbsp;·&nbsp;
  <b>{rec.side.value.upper()}{line_str}</b> &nbsp;·&nbsp;
  <b>{'%+d' % rec.american_odds}</b>
  &nbsp;&nbsp; {ev_badge(rec.ev_analysis.expected_value)}
  &nbsp; <span style="color:#aaa; font-size:0.85rem">Kelly: <b>{rec.recommended_units:.2f}u</b></span>
</p>
<p style="margin:0; color:#ccc; font-size:0.88rem">💬 {rec.summary}</p>
</div>
""", unsafe_allow_html=True)

                    with st.expander("🧠 View Chain-of-Thought Reasoning"):
                        for i, step in enumerate(rec.ev_analysis.reasoning_steps, 1):
                            st.markdown(f"**{i}.** {step}")
                        cols = st.columns(4)
                        cols[0].metric("Projected Prob", f"{rec.ev_analysis.projected_win_probability:.1%}")
                        cols[1].metric("Implied Prob", f"{rec.ev_analysis.implied_probability:.1%}")
                        cols[2].metric("EV", f"{rec.ev_analysis.expected_value:+.1%}")
                        cols[3].metric("Confidence", f"{rec.ev_analysis.confidence:.0%}")

                    if not dry_run:
                        a_col, r_col, _ = st.columns([1, 1, 4])
                        bet_key = rec.game_id + rec.bet_type.value + rec.side.value
                        if a_col.button("✅ Approve", key=f"approve_{bet_key}", use_container_width=True):
                            bet_id = ledger.save_recommendation(rec)
                            ledger.approve_bet(bet_id)
                            st.success(f"Bet saved and approved! ID: `{bet_id[:8]}`")
                            st.rerun()
                        if r_col.button("❌ Reject", key=f"reject_{bet_key}", use_container_width=True):
                            st.toast("Bet rejected — skipped.", icon="❌")

                    st.markdown("---")


# ── TAB 2: Pending Bets ────────────────────────────────────────────────────────
with tab_pending:
    pending = list(ledger.db["bets"].rows_where("status IN ('pending','approved')", []))

    if not pending:
        st.info("No pending or approved bets.")
    else:
        for bet in pending:
            status_icon = "✅ Approved" if bet["status"] == "approved" else "🕐 Pending"
            with st.expander(
                f"{status_icon} · {bet['away_team']} @ {bet['home_team']} — "
                f"{bet['bet_type'].upper()} {bet['side'].upper()} {('%+d' % bet['american_odds'])} "
                f"| EV: {bet['expected_value']:+.1%} | {bet['recommended_units']:.2f}u"
            ):
                st.markdown(f"**ID:** `{bet['id'][:8]}`  \n**Summary:** {bet['summary']}")

                if bet["status"] == "pending":
                    if st.button("✅ Approve", key=f"pend_approve_{bet['id'][:8]}"):
                        ledger.approve_bet(bet["id"])
                        st.success("Approved!")
                        st.rerun()

                st.markdown("**Settle this bet:**")
                scol1, scol2, scol3 = st.columns([2, 2, 1])
                result = scol1.selectbox("Result", ["win", "loss", "push"], key=f"res_{bet['id'][:8]}")
                pl = scol2.number_input("Profit/Loss (units)", value=float(bet["recommended_units"]),
                                        step=0.01, key=f"pl_{bet['id'][:8]}")
                if scol3.button("Settle", key=f"settle_{bet['id'][:8]}"):
                    ledger.settle_bet(bet["id"], result, pl if result != "loss" else -abs(pl))
                    st.success(f"Settled as {result.upper()}!")
                    st.rerun()


# ── TAB 3: History ─────────────────────────────────────────────────────────────
with tab_history:
    h_col1, h_col2 = st.columns([1, 2])

    with h_col1:
        st.markdown("### 💰 Bankroll")
        bankroll = ledger.get_bankroll()
        st.metric("Balance", f"{bankroll['balance_units']:.1f}u",
                  delta=f"${bankroll['balance_units'] * bankroll['unit_dollar_value']:.2f}")
        st.metric("Unit Size", f"${bankroll['unit_dollar_value']:.2f}")
        st.metric("Record", f"{wins}W – {losses}L")
        st.metric("All-time P/L", f"{total_pl:+.2f}u")

    with h_col2:
        st.markdown("### 📜 Settled Bets")
        if not settled:
            st.info("No settled bets yet.")
        else:
            rows = []
            for b in settled:
                rows.append({
                    "Game": f"{b['away_team']} @ {b['home_team']}",
                    "Bet": f"{b['bet_type'].upper()} {b['side'].upper()}",
                    "Odds": f"{'%+d' % b['american_odds']}",
                    "Result": b["result"].upper() if b["result"] else "",
                    "P/L": f"{b['profit_loss']:+.2f}u" if b["profit_loss"] is not None else "",
                    "EV": f"{b['expected_value']:+.1%}",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)


# ── TAB 4: Game Search ─────────────────────────────────────────────────────────
with tab_search:
    st.markdown("### 🔍 Game Search")
    st.markdown("Search by team name, conference, or any keyword to see live FanDuel odds.")

    # Initialize chat history
    if "search_messages" not in st.session_state:
        st.session_state.search_messages = []
    if "all_games" not in st.session_state:
        st.session_state.all_games = None

    # Display past chat messages
    for msg in st.session_state.search_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # Chat input
    query = st.chat_input("Search a team, conference, or phrase… e.g. 'UConn', 'Big East', 'Kansas'")

    if query:
        # Echo user message
        st.session_state.search_messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        with st.chat_message("assistant"):
            with st.spinner("Searching live slate..."):

                # Fetch games if not already cached
                if st.session_state.all_games is None:
                    try:
                        st.session_state.all_games = get_live_games(ledger)
                    except Exception as e:
                        err = f"⚠️ Couldn't fetch live games: {e}"
                        st.error(err)
                        st.session_state.search_messages.append({"role": "assistant", "content": err})
                        st.stop()

                all_games = st.session_state.all_games
                q = query.lower().strip()

                # Filter games: match team names, conference, or game_id
                matches = []
                for g in all_games:
                    searchable = " ".join(filter(None, [
                        g.home_team, g.away_team,
                        g.home_stats.conference if g.home_stats else "",
                        g.away_stats.conference if g.away_stats else "",
                        g.game_id,
                    ])).lower()
                    if q in searchable:
                        matches.append(g)

                if not matches:
                    reply = f"❌ No games found matching **\"{query}\"** on today's FanDuel slate."
                    st.markdown(reply)
                    st.session_state.search_messages.append({"role": "assistant", "content": reply})
                else:
                    reply_lines = [f"Found **{len(matches)} game(s)** matching **\"{query}\"**:\n"]
                    st.markdown(reply_lines[0])

                    for g in matches:
                        tip = g.game_time.strftime("%I:%M %p ET") if g.game_time else ""

                        # Build odds summary
                        spread_line = ""
                        if g.home_odds and g.away_odds:
                            spread_line = (
                                f"Spread: {g.home_team} {g.home_odds.line:+.1f} "
                                f"({'%+d' % g.home_odds.american_odds}) / "
                                f"{g.away_team} {g.away_odds.line:+.1f} "
                                f"({'%+d' % g.away_odds.american_odds})"
                            )

                        total_line = ""
                        if g.total_over_odds and g.total_under_odds:
                            total_line = (
                                f"Total: O/U {g.total_over_odds.line} "
                                f"(O {'%+d' % g.total_over_odds.american_odds} / "
                                f"U {'%+d' % g.total_under_odds.american_odds})"
                            )

                        conf_tag = ""
                        if g.home_stats and g.home_stats.conference:
                            conf_tag = f" · {g.home_stats.conference}"

                        card_md = f"""
<div class="bet-card" style="border-left-color:#5b8dee">
<h4 style="margin:0 0 0.3rem 0">
  {g.away_team} <span style="color:#888">@</span> {g.home_team}
  <span style="font-size:0.75rem; color:#888; font-weight:400; margin-left:8px">{tip}{conf_tag}</span>
</h4>
<p style="margin:0.2rem 0; color:#ccc; font-size:0.9rem">📊 {spread_line}</p>
<p style="margin:0.2rem 0; color:#ccc; font-size:0.9rem">🎯 {total_line}</p>
</div>"""
                        st.markdown(card_md, unsafe_allow_html=True)
                        reply_lines.append(f"• {g.away_team} @ {g.home_team} — {spread_line} | {total_line}")

                    full_reply = "\n".join(reply_lines)
                    st.session_state.search_messages.append({"role": "assistant", "content": full_reply})

    # Clear chat button
    if st.session_state.search_messages:
        if st.button("🗑 Clear Search History", key="clear_search"):
            st.session_state.search_messages = []
            st.rerun()

