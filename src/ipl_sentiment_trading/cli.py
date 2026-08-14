from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.data.loaders import (
    CORPUS_GAPS,
    MissingMatchError,
    available_match_ids,
)
from ipl_sentiment_trading.data.schema import MatchLoadError
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
    handle.write(f"- Narrative: {result.narrative_provider}\n")
    handle.write("\nFees and slippage are 0 in this book.\n")
    handle.write("\n## Intervals\n\n")
    for row in result.intervals:
        handle.write(f"### {row.name} · {row.start_time:%H:%M}–{row.end_time:%H:%M}\n\n")
        phase = "pregame" if row.is_pregame else ("innings break" if row.is_innings_break else f"innings {row.cricket.innings}")
        handle.write(f"- Phase: {phase}\n")
        c = row.cricket
        if not row.is_pregame and c.batting_team:
            handle.write(
                f"- Cricket: {c.batting_team} {c.innings_runs}/{c.innings_wickets} "
                f"({c.overs_str()} ov) RR {c.run_rate:.2f}; "
                f"dot {c.dot_ball_pct:.1%} (legal 0-run, wickets included); "
                f"boundary balls {c.boundary_ball_pct:.1%}; "
                f"boundary run share {c.boundary_run_share:.1%}; "
                f"partnership {c.partnership_runs} ({c.partnership_legal_balls} balls)\n"
            )
        else:
            handle.write("- Cricket: no balls in this interval\n")
        m = row.market
        if m:
            handle.write(
                f"- Market as of {m.as_of:%H:%M:%S}: "
                f"{a} decimal {m.decimal[result.team_a]:.2f} → raw {m.p_raw[result.team_a]:.3%} "
                f"fair {m.p_fair[result.team_a]:.3%}; "
                f"{b} decimal {m.decimal[result.team_b]:.2f} → raw {m.p_raw[result.team_b]:.3%} "
                f"fair {m.p_fair[result.team_b]:.3%}; "
                f"overround {m.overround:.2%}\n"
            )
        else:
            handle.write("- Market: no snapshot at or before interval end\n")
        s = row.sentiment
        handle.write(
            f"- Sentiment: {a} mean {s.team_a.mean:+.3f} (n={s.team_a.volume}); "
            f"{b} mean {s.team_b.mean:+.3f} (n={s.team_b.volume}); "
            f"match-level {s.match_level.mean:+.3f} (n={s.match_level.volume}); "
            f"total comments {s.total_comments}\n"
        )
        sig = row.signal
        handle.write(
            f"- View: reason `{sig.reason}`"
        )
        if sig.p_view_a is not None and sig.p_market_a is not None:
            handle.write(
                f"; p_market({a})={sig.p_market_a:.3%} p_sent={sig.p_sent_a:.3%} "
                f"p_view={sig.p_view_a:.3%} edge={sig.edge_a:+.2%} alpha={sig.alpha:.2f}"
            )
        handle.write("\n")
        if row.fill:
            f = row.fill
            handle.write(
                f"- Fill: back {f.team} @ {f.decimal_odds:.2f} stake {f.stake:.2f} "
                f"(Kelly* {f.kelly_raw:.3f})\n"
            )
        else:
            handle.write("- Fill: none\n")
        led = row.ledger
        handle.write(
            f"- Ledger: cash {led.cash:.2f}; exposure {led.exposure:.2f}; "
            f"equity {led.equity:.2f}; realized {led.realized_pnl:+.2f}\n"
        )
        if row.narrative:
            handle.write(f"\n{row.narrative}\n")
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
    try:
        result = analyze_match(
            args.match,
            data_root=data_root,
            params=params,
            narrative=args.narrative,
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
        description="IPL 2024 match-interval paper book (offline by default).",
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory containing chunks/ balls/ odds/")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list", help="List frozen match ids")
    list_p.set_defaults(func=_cmd_list)

    an = sub.add_parser("analyze", help="Analyze one match; no API key required")
    an.add_argument("match", help="Match id (e.g. 74) or path to a chunks JSON file")
    an.add_argument("-o", "--output", help="Write JSON or Markdown to this path")
    an.add_argument("--format", choices=("json", "md"), default="json")
    an.add_argument("--narrative", action="store_true", help="Call Gemini/Gemma only if a key or NARRATIVE_BASE_URL is set")
    an.add_argument("--bankroll", type=float, default=1000.0)
    an.set_defaults(func=_cmd_analyze)

    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not argv or argv[0] not in {"list", "analyze", "-h", "--help"}:
        # `ipl-analyze 74` and `ipl-analyze data/chunks/74.json out.md` (legacy two-arg)
        if argv and argv[0] not in {"-h", "--help"}:
            if len(argv) >= 2 and not argv[0].startswith("-") and not argv[1].startswith("-"):
                if argv[1].endswith(".md") or argv[1].endswith(".json"):
                    argv = ["analyze", argv[0], "-o", argv[1], "--format", "md" if argv[1].endswith(".md") else "json", *argv[2:]]
                else:
                    argv = ["analyze", *argv]
            else:
                argv = ["analyze", *argv]
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(2)
    sys.exit(args.func(args))


def ui_main() -> None:
    load_dotenv()
    from streamlit.web import cli as stcli

    app = Path(__file__).resolve().parent / "ui" / "app.py"
    sys.argv = ["streamlit", "run", str(app), *sys.argv[1:]]
    sys.exit(stcli.main())
