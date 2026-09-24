from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.corpus.loader import (
    CORPUS_GAPS,
    MissingMatchError,
    available_match_ids,
)
from ipl_sentiment_trading.corpus.schema import MatchLoadError
from ipl_sentiment_trading.pipeline.analyze import analyze_match


def _data_root_from_env() -> Path | None:
    raw = os.getenv("IPL_DATA_DIR")
    return Path(raw) if raw else None


def write_markdown(result, handle) -> None:
    a, b = result.team_a_abbr, result.team_b_abbr
    handle.write(f"# IPL 2024 paper book — match {result.match_id}\n\n")
    handle.write(f"**{result.team_a} vs {result.team_b}**")
    bits = [x for x in (result.round, result.date, result.venue) if x]
    if bits:
        handle.write(" · " + " · ".join(bits))
    handle.write("\n\n")
    handle.write(
        f"Settlement winner (frozen result, not a live feature): {result.winner or 'unknown'}\n\n"
    )
    if result.missing_xi:
        handle.write("Playing XI is not in the corpus.\n\n")
    handle.write("## Book\n\n")
    handle.write(f"- Starting bankroll: {result.starting_bankroll:.2f}\n")
    handle.write(f"- Ending equity: {result.ending_equity:.2f}\n")
    handle.write(f"- Settled PnL: {result.realized_pnl:+.2f}\n")
    handle.write(f"- Max drawdown: {result.max_drawdown:.1%} ({result.max_drawdown_abs:.2f})\n")
    handle.write(f"- Fills: {result.n_fills}\n")
    if result.hit_rate is not None:
        handle.write(f"- Hit rate (settled winners): {result.hit_rate:.1%} ({result.n_hits}/{result.n_fills})\n")
    handle.write(f"- Sentiment engine: {result.sentiment_source}\n")
    handle.write(f"- Narrative: {result.narrative_provider}\n")
    if result.jev_usage:
        u = result.jev_usage
        handle.write(
            f"- Jev decisions: {u.get('calls', 0)} calls "
            f"({u.get('cache_hits', 0)} cached), "
            f"{u.get('questions', 0)} questions, "
            f"~{u.get('input_tokens', 0)} input tokens, "
            f"{u.get('latency_ms', 0):.0f} ms total\n"
        )
    handle.write("\nFees and slippage are 0 in this book.\n")
    handle.write("\n## Intervals\n\n")
    for row in result.intervals:
        handle.write(f"### {row.name} · {row.start_time:%H:%M}–{row.end_time:%H:%M}\n\n")
        phase = "pregame" if row.is_pregame else (
            "innings break" if row.is_innings_break else f"innings {row.cricket.innings}"
        )
        handle.write(f"- Phase: {phase}\n")
        c = row.cricket
        if not row.is_pregame and c.batting_team:
            handle.write(
                f"- Cricket: {c.batting_team} {c.innings_runs}/{c.innings_wickets} "
                f"({c.overs_str()} ov) RR {c.run_rate:.2f}; "
                f"dot {c.dot_ball_pct:.1%}; "
                f"boundary balls {c.boundary_ball_pct:.1%}; "
                f"partnership {c.partnership_runs} ({c.partnership_legal_balls} balls)\n"
            )
        else:
            handle.write("- Cricket: no balls in this interval\n")
        m = row.market
        if m:
            cf = " (carried forward)" if m.is_carry_forward else ""
            handle.write(
                f"- Market as of {m.as_of:%H:%M:%S}{cf}: "
                f"{a} decimal {m.decimal[result.team_a]:.2f} → fair {m.p_fair[result.team_a]:.1%}; "
                f"{b} decimal {m.decimal[result.team_b]:.2f} → fair {m.p_fair[result.team_b]:.1%}; "
                f"overround {m.overround:.2%}\n"
            )
        else:
            handle.write("- Market: no snapshot at or before interval end\n")
        s = row.sentiment
        extra = (
            f" [eff {s.team_a.effective_volume:.0f}/{s.team_b.effective_volume:.0f}]"
            if s.source == "jev" else ""
        )
        handle.write(
            f"- Sentiment ({s.source}): {a} mean {s.team_a.mean:+.3f} (n={s.team_a.volume}); "
            f"{b} mean {s.team_b.mean:+.3f} (n={s.team_b.volume}); "
            f"match-level {s.match_level.mean:+.3f}; "
            f"total comments {s.total_comments}{extra}\n"
        )
        v = s.interval_verdict
        if v:
            handle.write(
                f"- Jev: regime={v.regime} signal_quality={v.signal_quality:.1f} "
                f"odds_stale={v.odds_stale:.2f} narrate={v.narrate:.2f}\n"
            )
        sig = row.signal
        handle.write(f"- View: reason `{sig.reason}`")
        if sig.p_view_a is not None and sig.p_market_a is not None:
            handle.write(
                f"; p_market({a})={sig.p_market_a:.3%} p_sent={sig.p_sent_a:.3%} "
                f"p_view={sig.p_view_a:.3%} edge={sig.edge_a:+.2%} alpha={sig.alpha:.2f}"
            )
        handle.write("\n")
        if row.fill:
            f = row.fill
            gate = f" (gate p={f.gate.p_genuine:.2f})" if f.gate else ""
            handle.write(
                f"- Fill: back {f.team} @ {f.decimal_odds:.2f} stake {f.stake:.2f} "
                f"(Kelly* {f.kelly_raw:.3f}){gate}\n"
            )
        else:
            handle.write("- Fill: none\n")
        led = row.ledger
        handle.write(
            f"- Ledger: cash {led.cash:.2f}; exposure {led.exposure:.2f}; "
            f"equity {led.equity:.2f}; realized {led.realized_pnl:+.2f}\n"
        )
        if row.narrative:
            handle.write(f"\n> {row.narrative}\n")
        handle.write("\n")
    handle.write("## Formula notes\n\n")
    for key, note in result.formula_notes.items():
        handle.write(f"- **{key}**: {note}\n")


def _cmd_list(args: argparse.Namespace) -> int:
    try:
        root = args.data_dir or _data_root_from_env()
        ids = available_match_ids(root)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"{len(ids)} frozen matches in corpus. Missing: {', '.join(map(str, CORPUS_GAPS))}")
    print(" ".join(str(i) for i in ids))
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    params = TradingParams(starting_bankroll=args.bankroll)
    data_root = args.data_dir or _data_root_from_env()

    decide = None
    if args.decisions_jsonl or args.jev_cache:
        from ipl_sentiment_trading.jev.client import open_traced_client

        client = open_traced_client(
            trace_path=args.decisions_jsonl, cache_path=args.jev_cache
        )
        decide = client.decide

    try:
        result = analyze_match(
            args.match,
            data_root=data_root,
            params=params,
            sentiment=args.sentiment,
            narrate=args.narrative,
            sample_k=args.sample_k,
            decide=decide,
        )
    except (MissingMatchError, MatchLoadError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 1
    payload = result.model_dump(mode="json")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "md" or out.suffix.lower() in {".md", ".markdown"}:
            with out.open("w", encoding="utf-8") as handle:
                write_markdown(result, handle)
        else:
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {out}")
    else:
        if args.format == "md":
            write_markdown(result, sys.stdout)
        else:
            json.dump(payload, sys.stdout, indent=2)
            sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ipl-analyze",
        description="IPL 2024 sentiment-vs-market paper book; Jev decides, Gemma narrates.",
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory containing chunks/ balls/ odds/")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List frozen match ids")
    list_p.set_defaults(func=_cmd_list)

    an = sub.add_parser("analyze", help="Analyze one match")
    an.add_argument("match", help="Match id (e.g. 74) or path to a chunks JSON file")
    an.add_argument("-o", "--output", help="Write JSON or Markdown to this path")
    an.add_argument("--format", choices=("json", "md"), default="json")
    an.add_argument("--sentiment", choices=("auto", "jev", "vader", "none"), default="auto")
    an.add_argument("--sample-k", type=int, default=30, help="Candidate comments per interval for Jev")
    an.add_argument("--decisions-jsonl", type=Path, default=None,
                    help="Trace every Jev decide call to this JSONL file")
    an.add_argument("--jev-cache", type=Path, default=None,
                    help="Content-addressed Jev decision cache (makes reruns free)")
    an.add_argument("--narrative", action="store_true",
                    help="Gemma 4 prose on Jev-narrate-gated intervals (needs GEMINI_API_KEY)")
    an.add_argument("--bankroll", type=float, default=1000.0)
    an.set_defaults(func=_cmd_analyze)

    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv or argv[0] not in {"list", "analyze", "-h", "--help"}:
        if argv and argv[0] not in {"-h", "--help"}:
            if len(argv) >= 2 and not argv[0].startswith("-") and not argv[1].startswith("-"):
                if argv[1].endswith(".md") or argv[1].endswith(".json"):
                    argv = [
                        "analyze", argv[0], "-o", argv[1], "--format",
                        "md" if argv[1].endswith(".md") else "json", *argv[2:],
                    ]
                else:
                    argv = ["analyze", *argv]
            else:
                argv = ["analyze", *argv]
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(2)
    sys.exit(args.func(args))
