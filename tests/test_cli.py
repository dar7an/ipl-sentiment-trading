from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.factories import ball, chunk, comment, odds_entry, write_match


def test_cli_analyze_offline_writes_probabilities_and_pnl(tmp_path) -> None:
    comments = [comment("Thala for a reason, CSK") for _ in range(16)] + [
        comment("MI are terrible tonight, Mumbai Indians") for _ in range(6)
    ]
    write_match(
        tmp_path,
        8,
        team_a="Chennai Super Kings",
        team_b="Mumbai Indians",
        chunks=[
            chunk(
                "chunk_1",
                start="2024-05-01 07:00:00 PM",
                end="2024-05-01 07:05:00 PM",
                comments=comments,
                odds=[odds_entry("2024-05-01 07:04:00 PM IST", "Chennai Super Kings", 1.90, "Mumbai Indians", 1.90)],
                balls=[ball(batting="Chennai Super Kings", runs=1)],
            )
        ],
        winner_id=2,
        local_id=2,
        visitor_id=6,
    )
    out = tmp_path / "result.json"
    env = os.environ.copy()
    env.pop("GOOGLE_API_KEY", None)
    env.pop("GEMINI_API_KEY", None)
    env.pop("NARRATIVE_BASE_URL", None)
    env["IPL_DATA_DIR"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    proc = subprocess.run(
        [sys.executable, "-m", "ipl_sentiment_trading", "analyze", "8", "-o", str(out), "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert "realized_pnl" in payload
    assert "ending_equity" in payload
    assert payload["narrative_provider"] == "off"
    first = payload["intervals"][0]
    assert "p_fair" in (first["market"] or {})
    assert "live_features" in first
    assert "winner" not in first["live_features"]
    md = tmp_path / "result.md"
    proc_md = subprocess.run(
        [sys.executable, "-m", "ipl_sentiment_trading", "analyze", "8", "-o", str(md), "--format", "md"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc_md.returncode == 0, proc_md.stderr
    text = md.read_text()
    assert "fair" in text.lower()
    assert "PnL" in text or "pnl" in text.lower() or "Settled PnL" in text
    assert "Trader Sentiment" not in text
