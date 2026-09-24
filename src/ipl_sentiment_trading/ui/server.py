"""FastAPI backend + static host for the React UI (`ipl-ui`).

Endpoints:
  GET /api/matches                       → [{match_id, label}]
  GET /api/analyze?match=&sentiment=&narrative=&bankroll=&trace=
                                           → AnalysisResult JSON (+ _trace rows)
  GET /*                                 → built web/dist assets (or 501 hint)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from ipl_sentiment_trading.config import TradingParams
from ipl_sentiment_trading.corpus.loader import available_match_ids
from ipl_sentiment_trading.pipeline.analyze import analyze_match

ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "web" / "dist"

app = FastAPI(title="ipl-sentiment-trading UI")


def _team_name(v: Any) -> str:
    return v.get("name", "?") if isinstance(v, dict) else str(v)


@app.get("/api/matches")
def matches() -> list[dict[str, Any]]:
    rows = []
    for mid in available_match_ids():
        try:
            info = json.loads((ROOT / "data" / "chunks" / f"{mid}.json").read_text()).get(
                "match_info", {}
            )
            label = f"{mid} · {_team_name(info.get('team1', '?'))} vs {_team_name(info.get('team2', '?'))}"
        except (OSError, ValueError, KeyError):
            label = str(mid)
        rows.append({"match_id": mid, "label": label})
    return rows


@app.get("/api/analyze")
def analyze(
    match: int,
    sentiment: str = Query("auto", pattern="^(auto|jev|vader|none)$"),
    narrative: bool = False,
    bankroll: float = 1000.0,
    trace: bool = False,
) -> JSONResponse:
    decide = None
    trace_path: Path | None = None
    if os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API_KEY"):
        from ipl_sentiment_trading.jev.client import open_traced_client

        fd, raw = tempfile.mkstemp(prefix=f"jev_trace_{match}_", suffix=".jsonl")
        os.close(fd)
        trace_path = Path(raw)
        decide = open_traced_client(trace_path=trace_path).decide
    result = analyze_match(
        match,
        params=TradingParams(starting_bankroll=bankroll),
        sentiment=sentiment,
        narrate=narrative,
        decide=decide,
    )
    out = result.model_dump(mode="json")
    if trace and trace_path and trace_path.exists():
        out["_trace"] = [
            json.loads(line)
            for line in trace_path.read_text().splitlines()
            if line.strip()
        ]
    if trace_path:
        trace_path.unlink(missing_ok=True)
    return JSONResponse(out)


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    if not DIST.exists():
        print(
            f"web/dist not built — run `cd web && npm install && npm run build` "
            f"first; API still available at http://{host}:{port}/api/matches"
        )
    uvicorn.run(app, host=host, port=port)
