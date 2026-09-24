"""Streamlit replay for the IPL 2024 paper book — with a Jev decisions panel."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from plotly.subplots import make_subplots

load_dotenv(ROOT / ".env")

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.corpus.loader import (
    CORPUS_GAPS,
    available_match_ids,
)
from ipl_sentiment_trading.pipeline.analyze import analyze_match

TEAM_COLOR = {
    "CSK": "#E8B931", "MI": "#6FA8FF", "RCB": "#FF6B6B", "KKR": "#C9A0FF",
    "SRH": "#FF9A56", "DC": "#7EB6FF", "GT": "#8FD3C8", "LSG": "#F48FB1",
    "PBKS": "#FF8A80", "RR": "#F8BBD0",
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
        font={"color": FONT, "size": 13, "family": "Source Sans 3, IBM Plex Sans, sans-serif"},
        height=height,
        margin={"l": 48, "r": 16, "t": 48, "b": 48},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0, "bgcolor": "rgba(0,0,0,0)"},
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
div[data-testid="stMetric"] { background: #151D2E; border: 1px solid #243049; padding: 12px 14px; }
div[data-testid="stMetric"] label { color: #93A0B8 !important; }
hr { border-color: #243049; }
.kicker { color: #93A0B8; font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.2rem; }
.caption-src { color: #6D7A94; font-size: 0.75rem; margin-top: -0.4rem; }
section[data-testid="stSidebar"] { background: #0B1220; border-right: 1px solid #243049; }
.stAppDeployButton { display: none; }
header[data-testid="stHeader"] { background: transparent; }
.jev-chip { display:inline-block; background:#1A2338; border:1px solid #243049; border-radius:4px; padding:2px 8px; margin:2px 4px 2px 0; font-size:0.78rem; color:#D4A017; }
</style>
        """,
        unsafe_allow_html=True,
    )


def _have_jev_key() -> bool:
    return bool(os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY"))


def _have_gemini_key() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


@st.cache_data(show_spinner=False)
def _catalog() -> list[dict]:
    rows = []
    for mid in available_match_ids():
        try:
            path = Path("data/chunks") / f"{mid}.json"
            info = json.loads(path.read_text()).get("match_info", {})
            a, b = info.get("team1", "?"), info.get("team2", "?")
            rows.append({"match_id": mid, "label": f"{mid} · {a} vs {b}"})
        except (OSError, ValueError, KeyError):
            rows.append({"match_id": mid, "label": str(mid)})
    return rows


@st.cache_data(show_spinner="Analyzing frozen intervals…")
def _analyze(match_id: int, bankroll: float, sentiment: str, use_trace: bool) -> dict:
    decide = None
    tracer_path = None
    if use_trace:
        from ipl_sentiment_trading.jev.client import open_traced_client

        tracer_path = Path(tempfile.gettempdir()) / f"jev_trace_{match_id}.jsonl"
        client = open_traced_client(trace_path=tracer_path)
        decide = client.decide
    result = analyze_match(
        match_id,
        params=TradingParams(starting_bankroll=bankroll),
        sentiment=sentiment,
        narrate=False,
        decide=decide,
    )
    out = result.model_dump(mode="json")
    if tracer_path and tracer_path.exists():
        out["_trace"] = [
            json.loads(line) for line in tracer_path.read_text().splitlines() if line.strip()
        ]
    return out


def _header(result: dict) -> None:
    kicker = " · ".join(x for x in (result.get("round"), result.get("date"), result.get("venue")) if x)
    st.markdown('<div class="kicker">IPL 2024 paper book · Jev-decided</div>', unsafe_allow_html=True)
    st.title(f"{result['team_a']} vs {result['team_b']}")
    if kicker:
        st.caption(kicker)
    st.caption(f"Sentiment engine: **{result.get('sentiment_source','?')}** · narrative: {result.get('narrative_provider','off')}")


def _market_chart(result: dict, cursor: int) -> go.Figure:
    a, b = result["team_a_abbr"], result["team_b_abbr"]
    xs, fair_a, fair_b, view_a = [], [], [], []
    for i, row in enumerate(result["intervals"]):
        m = row.get("market")
        xs.append(i + 1)
        fair_a.append(m["p_fair"][result["team_a"]] * 100 if m else None)
        fair_b.append(m["p_fair"][result["team_b"]] * 100 if m else None)
        v = row["signal"].get("p_view_a")
        view_a.append(v * 100 if v is not None else None)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=fair_a, name=f"{a} fair p*", mode="lines", line={"color": _color(a, "#6FA8FF"), "width": 2.4}))
    fig.add_trace(go.Scatter(x=xs, y=fair_b, name=f"{b} fair p*", mode="lines", line={"color": _color(b, "#FF9A56"), "width": 2.4}))
    fig.add_trace(go.Scatter(x=xs, y=view_a, name=f"{a} p_view (sentiment)", mode="lines", line={"color": ACCENT, "width": 2, "dash": "dot"}))
    fig.add_vline(x=cursor, line_width=1, line_dash="dash", line_color=ACCENT)
    fig.update_yaxes(title_text="Win probability (%)", rangemode="tozero")
    fig.update_xaxes(title_text="Interval index")
    fig.update_layout(title="De-vigged market p* vs Jev-adjusted view p_view")
    return _apply_layout(fig, height=340)


def _sentiment_chart(result: dict, cursor: int) -> go.Figure:
    a, b = result["team_a_abbr"], result["team_b_abbr"]
    xs = list(range(1, len(result["intervals"]) + 1))
    sa = [row["sentiment"]["team_a"]["mean"] for row in result["intervals"]]
    sb = [row["sentiment"]["team_b"]["mean"] for row in result["intervals"]]
    ea = [row["sentiment"]["team_a"].get("effective_volume") or row["sentiment"]["team_a"]["volume"] for row in result["intervals"]]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=xs, y=sa, name=f"{a} crowd lean", line={"color": _color(a, "#6FA8FF"), "width": 2}), secondary_y=False)
    fig.add_trace(go.Scatter(x=xs, y=sb, name=f"{b} crowd lean", line={"color": _color(b, "#FF9A56"), "width": 2}), secondary_y=False)
    fig.add_trace(go.Bar(x=xs, y=ea, name=f"{a} effective volume", marker_color="rgba(212,160,23,0.25)", opacity=0.8), secondary_y=True)
    fig.add_vline(x=cursor, line_width=1, line_dash="dash", line_color=ACCENT)
    fig.update_yaxes(title_text="Crowd lean (−1 to 1)", range=[-1, 1], secondary_y=False)
    fig.update_yaxes(title_text="Effective volume", secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text="Interval index")
    fig.update_layout(title=f"Jev verdicts aggregated ({result.get('sentiment_source','?')}) — weighted by relevance, team-prob, upvotes")
    return _apply_layout(fig, height=340)


def _equity_chart(result: dict, cursor: int) -> go.Figure:
    xs = list(range(1, len(result["intervals"]) + 1))
    eq = [row["ledger"]["equity"] for row in result["intervals"]]
    cash = [row["ledger"]["cash"] for row in result["intervals"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=eq, name="Equity (cash + MTM)", line={"color": ACCENT, "width": 2.4}))
    fig.add_trace(go.Scatter(x=xs, y=cash, name="Cash", line={"color": MUTED, "width": 1.5, "dash": "dot"}))
    fig.add_hline(y=result["starting_bankroll"], line_color=GRID, line_dash="dash", annotation_text="start")
    fig.add_vline(x=cursor, line_width=1, line_dash="dash", line_color="#E8EEF7")
    fills_x, fills_y = [], []
    for i, item in enumerate(result["intervals"], start=1):
        if item.get("fill"):
            fills_x.append(i)
            fills_y.append(item["ledger"]["equity"])
    if fills_x:
        fig.add_trace(go.Scatter(x=fills_x, y=fills_y, name="Fill", mode="markers",
                               marker={"size": 9, "color": "#E8EEF7", "symbol": "diamond", "line": {"width": 1, "color": ACCENT}}))
    fig.update_yaxes(title_text="Paper units")
    fig.update_xaxes(title_text="Interval index")
    fig.update_layout(title="Paper equity path (fees = 0, Jev gate applied)")
    return _apply_layout(fig, height=320)


def _jev_panel(result: dict, cursor: int) -> None:
    """The Jev decisions panel — every typed verdict the engine produced."""
    row = result["intervals"][cursor - 1]
    sent = row["sentiment"]
    verdict = sent.get("interval_verdict")
    st.subheader("Jev decisions — this interval")
    if verdict:
        chips = (
            f"<span class='jev-chip'>regime: {verdict['regime']}</span>"
            f"<span class='jev-chip'>signal_quality: {verdict['signal_quality']:.1f}/5</span>"
            f"<span class='jev-chip'>odds_stale: {verdict['odds_stale']:.2f}</span>"
            f"<span class='jev-chip'>narrate: {verdict['narrate']:.2f}</span>"
        )
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.caption("No interval verdict (vader/none engine).")
    vrows = []
    for v in sent.get("verdicts") or []:
        vrows.append({
            "comment": v["index"],
            "relevant": round(v["relevant"], 2),
            "side": v["team"],
            "p(side)": round(max(v["team_probs"].values() or [0]), 2),
            "bullish": round(v["bullish"], 1),
        })
    if vrows:
        st.dataframe(pd.DataFrame(vrows), width="stretch", hide_index=True, height=220)
    fill = row.get("fill")
    if fill and fill.get("gate"):
        g = fill["gate"]
        st.caption(f"Trade gate: {'approved' if g['approved'] else 'vetoed'} (p_genuine={g['p_genuine']:.2f})")

    trace = result.get("_trace") or []
    if trace:
        st.subheader("Jev decision trace — match")
        trows = [
            {
                "i": i + 1,
                "questions": e.get("n_questions", len(e.get("questions") or {})),
                "cache": "hit" if e.get("cache_hit") else "api",
                "tokens": (e.get("usage") or {}).get("input_tokens", 0),
                "ms": round(e.get("latency_ms") or 0),
            }
            for i, e in enumerate(trace)
        ]
        st.dataframe(pd.DataFrame(trows), width="stretch", hide_index=True, height=180)


def main() -> None:
    st.set_page_config(page_title="IPL 2024 paper book", layout="wide", initial_sidebar_state="expanded")
    _inject_css()
    catalog = _catalog()
    if not catalog:
        st.error("No frozen matches found under data/chunks.")
        return
    labels = {row["label"]: row["match_id"] for row in catalog}
    with st.sidebar:
        st.markdown("**Match**")
        default_label = next((k for k, v in labels.items() if v == 74), catalog[0]["label"])
        choice = st.selectbox("Frozen 2024 corpus", options=list(labels),
                              index=list(labels).index(default_label) if default_label in labels else 0)
        match_id = labels[choice]
        bankroll = st.number_input("Starting bankroll", min_value=100.0, value=1000.0, step=100.0)
        st.caption(f"Gaps in corpus: {', '.join(str(g) for g in CORPUS_GAPS)}")
        engines = ["auto", "jev", "vader", "none"]
        sentiment = st.selectbox("Sentiment engine", engines, index=0)
        if sentiment in {"auto", "jev"} and not _have_jev_key():
            st.warning("No TYPESAFE_API_KEY/JEV_API_KEY — 'auto' falls back to VADER.")
        use_trace = st.toggle("Trace Jev decisions", value=True,
                              help="Writes every decide call to a temp JSONL; shown below.")
        st.markdown("---")
        st.markdown("**How to read this**")
        st.caption(
            "Jev types each judgment: per-comment relevance/side/bullishness in ONE batched "
            "call per interval, interval regime + signal quality, a guardrail noul before "
            "every fill, and drama routing for narration. Arithmetic stays deterministic: "
            "de-vig, log-odds update, Kelly caps, settlement."
        )

    result = _analyze(match_id, float(bankroll), sentiment, use_trace and _have_jev_key())
    _header(result)

    n = len(result["intervals"])
    cursor = st.slider("Replay interval", min_value=1, max_value=n, value=1,
                       help="Arrow keys work when this control is focused.")
    row = result["intervals"][cursor - 1]
    phase = "Pregame" if row["is_pregame"] else ("Innings break" if row["is_innings_break"] else f"Innings {row['cricket']['innings']}")
    st.markdown(f"**{row['name']}** · {row['start_time'][11:16]}–{row['end_time'][11:16]} · {phase}")

    c1, c2, c3, c4, c5 = st.columns(5)
    m = row.get("market")
    a_name, b_name = result["team_a"], result["team_b"]
    if m:
        c1.metric(f"{result['team_a_abbr']} fair p*", f"{m['p_fair'][a_name]*100:.1f}%")
        c2.metric(f"{result['team_b_abbr']} fair p*", f"{m['p_fair'][b_name]*100:.1f}%")
        c3.metric("Overround", f"{m['overround']*100:.2f}%")
    else:
        c1.metric(f"{result['team_a_abbr']} fair p*", "—")
        c2.metric(f"{result['team_b_abbr']} fair p*", "—")
        c3.metric("Overround", "—")
    eq_delta = row["ledger"]["equity"] - result["starting_bankroll"]
    c4.metric("Equity", f"{row['ledger']['equity']:.1f}",
              delta=None if abs(eq_delta) < 0.05 else f"{eq_delta:+.1f}")
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
                f"Dot % {cricket['dot_ball_pct']*100:.1f} · "
                f"Boundary % {cricket['boundary_ball_pct']*100:.1f} · "
                f"Partnership {cricket['partnership_runs']} ({cricket['partnership_legal_balls']} balls)"
            )
        sig = row["signal"]
        st.subheader("Paper signal")
        st.write(f"Reason: `{sig['reason']}`")
        if sig.get("p_view_a") is not None:
            st.write(
                f"p*={sig['p_market_a']:.1%} · p_sent={sig['p_sent_a']:.1%} · "
                f"p_view={sig['p_view_a']:.1%} · edge={sig['edge_a']:+.1%} · α={sig['alpha']:.2f}"
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
            f"{result['team_a_abbr']} {s['team_a']['mean']:+.3f} (n={s['team_a']['volume']}, eff {s['team_a'].get('effective_volume',0):.0f}) · "
            f"{result['team_b_abbr']} {s['team_b']['mean']:+.3f} (n={s['team_b']['volume']})"
        )
        quotes = [q for q in (s["team_a"].get("sample_positive") or [])[:2]
                  + (s["team_b"].get("sample_negative") or [])[:1] if q]
        if quotes:
            with st.expander("Sample attributed comments"):
                for q in quotes:
                    st.caption(q)
        if row.get("narrative"):
            st.write(f"> {row['narrative']}")

    st.plotly_chart(_market_chart(result, cursor), width="stretch")
    c_sent, c_eq = st.columns(2)
    with c_sent:
        st.plotly_chart(_sentiment_chart(result, cursor), width="stretch")
    with c_eq:
        st.plotly_chart(_equity_chart(result, cursor), width="stretch")

    _jev_panel(result, cursor)

    st.subheader("Ledger")
    book_cols = st.columns(4)
    book_cols[0].metric("Settled PnL", f"{result['realized_pnl']:+.2f}")
    book_cols[1].metric("Fills", str(result["n_fills"]))
    book_cols[2].metric("Hit rate", "—" if result["hit_rate"] is None else f"{result['hit_rate']*100:.0f}%")
    book_cols[3].metric("Max drawdown", f"{result['max_drawdown']*100:.1f}%")
    usage = result.get("jev_usage") or {}
    if usage:
        st.caption(
            f"Jev: {usage.get('calls',0)} decide calls ({usage.get('cache_hits',0)} cached) · "
            f"{usage.get('questions',0)} questions · ~{usage.get('input_tokens',0)} input tokens"
        )
    ledger_rows = [
        {
            "i": i,
            "interval": item["name"],
            "cash": round(item["ledger"]["cash"], 2),
            "exposure": round(item["ledger"]["exposure"], 2),
            "equity": round(item["ledger"]["equity"], 2),
            "fill": None if not item.get("fill") else f"{item['fill'].get('team')} @ {item['fill'].get('decimal_odds')}",
            "gate": None if not (item.get("fill") or {}).get("gate") else round(item["fill"]["gate"]["p_genuine"], 2),
        }
        for i, item in enumerate(result["intervals"], start=1)
    ]
    st.dataframe(pd.DataFrame(ledger_rows), width="stretch", hide_index=True, height=280)
    st.caption("Identity: cash + exposure = starting bankroll + realized PnL while fees are 0. Last interval settles remaining fills on the frozen winner.")

    with st.expander("Settlement (not a live feature)"):
        st.write(f"Frozen winner: **{result.get('winner') or 'unknown'}**")
        st.caption("Winner is applied only after the final interval's live decision. Interval charts and signals never see it.")


if __name__ == "__main__":
    main()
