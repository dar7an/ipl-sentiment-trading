"""Streamlit replay for the IPL 2024 paper book."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.data.loaders import CORPUS_GAPS, load_catalog
from ipl_sentiment_trading.narrative import narrative_credentials_present
from ipl_sentiment_trading.pipeline.analyze import analyze_match

TEAM_COLOR = {
    "CSK": "#E8B931",
    "MI": "#6FA8FF",
    "RCB": "#FF6B6B",
    "KKR": "#C9A0FF",
    "SRH": "#FF9A56",
    "DC": "#7EB6FF",
    "GT": "#8FD3C8",
    "LSG": "#F48FB1",
    "PBKS": "#FF8A80",
    "RR": "#F8BBD0",
}

PLOT_BG = "#0B1220"
GRID = "#243049"
FONT = "#E8EEF7"
MUTED = "#93A0B8"
ACCENT = "#D4A017"


def _color(abbr: str, fallback: str) -> str:
    return TEAM_COLOR.get(abbr, fallback)


def _apply_layout(fig: go.Figure, *, height: int = 320) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=PLOT_BG,
        font=dict(color=FONT, size=13, family="Source Sans 3, IBM Plex Sans, sans-serif"),
        height=height,
        margin=dict(l=48, r=16, t=48, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def _inject_css() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@600&display=swap');
html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1180px; }
h1, h2, h3 { font-family: "IBM Plex Serif", Georgia, serif; letter-spacing: -0.02em; }
h1 { font-size: 1.7rem !important; font-weight: 600 !important; }
h2 { font-size: 1.15rem !important; margin-top: 0.4rem !important; }
h3 { font-size: 0.95rem !important; color: #93A0B8 !important; font-family: "IBM Plex Sans", sans-serif !important; font-weight: 600 !important; letter-spacing: 0.04em; text-transform: uppercase; }
div[data-testid="stMetric"] {
  background: #151D2E;
  border: 1px solid #243049;
  padding: 12px 14px;
}
div[data-testid="stMetric"] label { color: #93A0B8 !important; }
hr { border-color: #243049; }
.kicker { color: #93A0B8; font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.2rem; }
.caption-src { color: #6D7A94; font-size: 0.75rem; margin-top: -0.4rem; }
section[data-testid="stSidebar"] { background: #0B1220; border-right: 1px solid #243049; }
.stAppDeployButton { display: none; }
header[data-testid="stHeader"] { background: transparent; }
</style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _catalog():
    return load_catalog()


@st.cache_data(show_spinner="Analyzing frozen intervals (VADER + paper book)…")
def _analyze(match_id: int, bankroll: float) -> dict:
    result = analyze_match(match_id, params=TradingParams(starting_bankroll=bankroll), narrative=False)
    return result.model_dump(mode="json")


def _header(result: dict) -> None:
    kicker = " · ".join(x for x in (result.get("round"), result.get("date"), result.get("venue")) if x)
    st.markdown('<div class="kicker">IPL 2024 paper book</div>', unsafe_allow_html=True)
    st.title(f"{result['team_a']} vs {result['team_b']}")
    if kicker:
        st.caption(kicker)
    if result.get("missing_xi"):
        st.caption("Playing XI is not in this corpus — omitted on purpose.")


def _market_chart(result: dict, cursor: int) -> go.Figure:
    a, b = result["team_a_abbr"], result["team_b_abbr"]
    xs, fair_a, fair_b, raw_a, raw_b, over = [], [], [], [], [], []
    for i, row in enumerate(result["intervals"]):
        m = row.get("market")
        xs.append(i + 1)
        if not m:
            fair_a.append(None)
            fair_b.append(None)
            raw_a.append(None)
            raw_b.append(None)
            over.append(None)
            continue
        fair_a.append(m["p_fair"][result["team_a"]] * 100)
        fair_b.append(m["p_fair"][result["team_b"]] * 100)
        raw_a.append(m["p_raw"][result["team_a"]] * 100)
        raw_b.append(m["p_raw"][result["team_b"]] * 100)
        over.append(m["overround"] * 100)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=fair_a, name=f"{a} fair p*", mode="lines", line=dict(color=_color(a, "#6FA8FF"), width=2.4)))
    fig.add_trace(go.Scatter(x=xs, y=fair_b, name=f"{b} fair p*", mode="lines", line=dict(color=_color(b, "#FF9A56"), width=2.4)))
    fig.add_trace(go.Scatter(x=xs, y=raw_a, name=f"{a} raw 1/d", mode="lines", line=dict(color=_color(a, "#6FA8FF"), width=1, dash="dot")))
    fig.add_trace(go.Scatter(x=xs, y=raw_b, name=f"{b} raw 1/d", mode="lines", line=dict(color=_color(b, "#FF9A56"), width=1, dash="dot")))
    fig.add_vline(x=cursor, line_width=1, line_dash="dash", line_color=ACCENT)
    fig.update_yaxes(title_text="Win probability (%)", rangemode="tozero")
    fig.update_xaxes(title_text="Interval index")
    fig.update_layout(title="De-vigged win probability vs raw implied (1/decimal)")
    return _apply_layout(fig, height=340)


def _sentiment_chart(result: dict, cursor: int) -> go.Figure:
    a, b = result["team_a_abbr"], result["team_b_abbr"]
    xs = list(range(1, len(result["intervals"]) + 1))
    sa = [row["sentiment"]["team_a"]["mean"] for row in result["intervals"]]
    sb = [row["sentiment"]["team_b"]["mean"] for row in result["intervals"]]
    va = [row["sentiment"]["team_a"]["volume"] for row in result["intervals"]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=xs, y=sa, name=f"{a} VADER mean", line=dict(color=_color(a, "#6FA8FF"), width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=xs, y=sb, name=f"{b} VADER mean", line=dict(color=_color(b, "#FF9A56"), width=2)), secondary_y=False)
    fig.add_trace(go.Bar(x=xs, y=va, name=f"{a} comment volume", marker_color="rgba(212,160,23,0.25)", opacity=0.8), secondary_y=True)
    fig.add_vline(x=cursor, line_width=1, line_dash="dash", line_color=ACCENT)
    fig.update_yaxes(title_text="Compound sentiment (−1 to 1)", range=[-1, 1], secondary_y=False)
    fig.update_yaxes(title_text="Attributed comments (count)", secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="Interval index")
    fig.update_layout(title="Team-attributed sentiment (volume-weighted buckets, not a match blob)")
    return _apply_layout(fig, height=340)


def _equity_chart(result: dict, cursor: int) -> go.Figure:
    xs = list(range(1, len(result["intervals"]) + 1))
    eq = [row["ledger"]["equity"] for row in result["intervals"]]
    cash = [row["ledger"]["cash"] for row in result["intervals"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=eq, name="Equity (cash + MTM)", line=dict(color=ACCENT, width=2.4)))
    fig.add_trace(go.Scatter(x=xs, y=cash, name="Cash", line=dict(color=MUTED, width=1.5, dash="dot")))
    fig.add_hline(y=result["starting_bankroll"], line_color=GRID, line_dash="dash", annotation_text="start")
    fig.add_vline(x=cursor, line_width=1, line_dash="dash", line_color="#E8EEF7")
    fills_x, fills_y = [], []
    for i, item in enumerate(result["intervals"], start=1):
        if item.get("fill"):
            fills_x.append(i)
            fills_y.append(item["ledger"]["equity"])
    if fills_x:
        fig.add_trace(
            go.Scatter(
                x=fills_x,
                y=fills_y,
                name="Fill",
                mode="markers",
                marker=dict(size=9, color="#E8EEF7", symbol="diamond", line=dict(width=1, color=ACCENT)),
            )
        )
    fig.update_yaxes(title_text="Paper units")
    fig.update_xaxes(title_text="Interval index")
    fig.update_layout(title="Paper equity path (fees = 0)")
    return _apply_layout(fig, height=320)


def main() -> None:
    st.set_page_config(page_title="IPL 2024 paper book", layout="wide", initial_sidebar_state="expanded")
    _inject_css()
    catalog = _catalog()
    if not catalog:
        st.error("No frozen matches found under data/chunks.")
        return
    labels = {row.label: row.match_id for row in catalog}
    with st.sidebar:
        st.markdown("**Match**")
        default_label = next((k for k, v in labels.items() if v == 74), catalog[0].label)
        choice = st.selectbox(
            "Frozen 2024 corpus",
            options=list(labels),
            index=list(labels).index(default_label) if default_label in labels else 0,
            help="71 matches. 63, 66, 70 were never dumped.",
        )
        match_id = labels[choice]
        bankroll = st.number_input("Starting bankroll", min_value=100.0, value=1000.0, step=100.0)
        st.caption(f"Gaps in corpus: {', '.join(str(g) for g in CORPUS_GAPS)}")
        want_narrative = st.toggle("LLM narrative sidecar", value=False, help="Off by default. Requires a key or NARRATIVE_BASE_URL; still not used for fills.")
        if want_narrative and not narrative_credentials_present():
            st.warning("Narrative stays off: no GOOGLE_API_KEY / GEMINI_API_KEY / NARRATIVE_BASE_URL in the environment.")
        st.markdown("---")
        st.markdown("**How to read this**")
        st.caption(
            "Market lines are proportional de-vig (p_raw = 1/decimal, p* = p_raw / sum). "
            "Sentiment updates log-odds of p*, not a 50/50 mix. Fills fire when |edge| ≥ 3% "
            "and volume clears the floor; same-side bets are not pyramided. "
            "Settlement uses the frozen winner only after the last live interval."
        )

    result = _analyze(match_id, float(bankroll))
    _header(result)

    n = len(result["intervals"])
    names = [row["name"] for row in result["intervals"]]
    cursor = st.slider("Replay interval", min_value=1, max_value=n, value=1, help="Arrow keys work when this control is focused.")
    row = result["intervals"][cursor - 1]
    phase = "Pregame" if row["is_pregame"] else ("Innings break" if row["is_innings_break"] else f"Innings {row['cricket']['innings']}")
    st.markdown(
        f"**{row['name']}** · {row['start_time'][11:16]}–{row['end_time'][11:16]} · {phase} · "
        f"{names[0]} to {names[-1]}"
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    m = row.get("market")
    a_name, b_name = result["team_a"], result["team_b"]
    if m:
        c1.metric(f"{result['team_a_abbr']} fair p*", f"{m['p_fair'][a_name]*100:.1f}%")
        c1.caption(f"raw implied {m['p_raw'][a_name]*100:.1f}%")
        c2.metric(f"{result['team_b_abbr']} fair p*", f"{m['p_fair'][b_name]*100:.1f}%")
        c2.caption(f"raw implied {m['p_raw'][b_name]*100:.1f}%")
        c3.metric("Overround", f"{m['overround']*100:.2f}%")
    else:
        c1.metric(f"{result['team_a_abbr']} fair p*", "—")
        c2.metric(f"{result['team_b_abbr']} fair p*", "—")
        c3.metric("Overround", "—")
    eq_delta = row["ledger"]["equity"] - result["starting_bankroll"]
    c4.metric(
        "Equity",
        f"{row['ledger']['equity']:.1f}",
        delta=None if abs(eq_delta) < 0.05 else f"{eq_delta:+.1f}",
    )
    c5.metric("Open exposure", f"{row['ledger']['exposure']:.1f}")

    cricket = row["cricket"]
    left, right = st.columns(2)
    with left:
        st.subheader("On the field")
        if row["is_pregame"] or not cricket.get("batting_team"):
            st.write("No balls in this interval.")
        else:
            st.write(
                f"{cricket['batting_team']} **{cricket['innings_runs']}/{cricket['innings_wickets']}** "
                f"({cricket['innings_legal_balls'] // 6}.{cricket['innings_legal_balls'] % 6} ov) · "
                f"RR {cricket['run_rate']:.2f}"
            )
            st.write(
                f"Dot ball % {cricket['dot_ball_pct']*100:.1f} (legal 0-run, wickets included) · "
                f"Boundary ball % {cricket['boundary_ball_pct']*100:.1f} · "
                f"Boundary run share {cricket['boundary_run_share']*100:.1f}"
            )
            st.write(
                f"Partnership {cricket['partnership_runs']} runs off {cricket['partnership_legal_balls']} legal balls "
                f"(carries across intervals until a wicket)."
            )
        sig = row["signal"]
        st.subheader("Paper signal")
        st.write(f"Reason: `{sig['reason']}`")
        if sig.get("p_view_a") is not None:
            st.write(
                f"p_market({result['team_a_abbr']})={sig['p_market_a']:.1%} · "
                f"p_sent={sig['p_sent_a']:.1%} · p_view={sig['p_view_a']:.1%} · "
                f"edge={sig['edge_a']:+.1%} · shrink α={sig['alpha']:.2f}"
            )
        if row.get("fill"):
            f = row["fill"]
            st.write(f"Fill: back **{f['team']}** @ {f['decimal_odds']:.2f} for {f['stake']:.2f} (0.25 Kelly, 5% cap).")
        else:
            st.write("No fill this interval.")
    with right:
        st.subheader("Crowd")
        s = row["sentiment"]
        st.write(
            f"{result['team_a_abbr']} mean {s['team_a']['mean']:+.3f} (n={s['team_a']['volume']}) · "
            f"{result['team_b_abbr']} mean {s['team_b']['mean']:+.3f} (n={s['team_b']['volume']}) · "
            f"unattributed {s['match_level']['mean']:+.3f} (n={s['match_level']['volume']})"
        )
        quotes = [
            q
            for q in (s["team_a"].get("sample_positive") or [])[:2]
            + (s["team_b"].get("sample_negative") or [])[:1]
            if q
        ]
        if quotes:
            with st.expander("Sample attributed comments"):
                for q in quotes:
                    st.caption(q)

    st.plotly_chart(_market_chart(result, cursor), width="stretch")
    st.markdown('<p class="caption-src">Source: FanDuel h2h prints in the frozen dump · latest snapshot at or before interval end · proportional de-vig.</p>', unsafe_allow_html=True)

    c_sent, c_eq = st.columns(2)
    with c_sent:
        st.plotly_chart(_sentiment_chart(result, cursor), width="stretch")
    with c_eq:
        st.plotly_chart(_equity_chart(result, cursor), width="stretch")

    st.subheader("Ledger")
    book_cols = st.columns(4)
    book_cols[0].metric("Settled PnL", f"{result['realized_pnl']:+.2f}")
    book_cols[1].metric("Fills", str(result["n_fills"]))
    book_cols[2].metric("Hit rate", "—" if result["hit_rate"] is None else f"{result['hit_rate']*100:.0f}%")
    book_cols[3].metric("Max drawdown", f"{result['max_drawdown']*100:.1f}%")
    ledger_rows = []
    for i, item in enumerate(result["intervals"], start=1):
        fill = item.get("fill") or {}
        ledger_rows.append(
            {
                "i": i,
                "interval": item["name"],
                "cash": round(item["ledger"]["cash"], 2),
                "exposure": round(item["ledger"]["exposure"], 2),
                "equity": round(item["ledger"]["equity"], 2),
                "fill": None if not fill else f"{fill.get('team')} @ {fill.get('decimal_odds')}",
                "stake": None if not fill else fill.get("stake"),
            }
        )
    st.dataframe(pd.DataFrame(ledger_rows), width="stretch", hide_index=True, height=280)
    st.caption("Identity: cash + exposure = starting bankroll + realized PnL while fees are 0. Last interval settles remaining fills on the frozen winner.")

    with st.expander("Narrative sidecar"):
        if not want_narrative:
            st.write("Disabled. The paper book does not need an LLM. Enable the sidebar toggle and set GEMINI_API_KEY or NARRATIVE_BASE_URL to attach prose to as-of-t features only.")
        elif not narrative_credentials_present():
            st.write("No key or NARRATIVE_BASE_URL is set, so nothing is called. Fills above are unchanged.")
        else:
            st.write("This UI run is cached without LLM calls. Use `ipl-analyze analyze 74 --narrative` for sidecar prose. Prompts never include the winner.")
        if row.get("narrative"):
            st.write(row["narrative"])

    with st.expander("Settlement (not a live feature)"):
        st.write(f"Frozen winner: **{result.get('winner') or 'unknown'}**")
        if result.get("winner_note"):
            st.caption(result["winner_note"])
        st.caption("Winner is applied only after the final interval's live decision. Interval charts and signals do not see it.")


if __name__ == "__main__":
    main()
