---
name: testing-ipl-app
description: How to run and verify the ipl-sentiment-trading CLI and web UI end-to-end (Jev API calls, VADER offline mode, expected call counts, known quirks).
---

# Testing ipl-sentiment-trading

## Devin Secrets Needed
- `TYPESAFE_API_KEY` — enables Jev decide calls (sentiment engine + trade gate). Without it `auto` falls back to VADER.
- `GEMINI_API_KEY` — only needed for `--narrative` / the Narrate checkbox (Gemma); skippable for speed.

## Setup
- venv is `.venv` (editable install done). Binaries: `.venv/bin/ipl-analyze`, `.venv/bin/ipl-ui`.
- VADER needs `nltk.download('vader_lexicon')` once (blueprint initialize covers it).
- UI is React+StyleX (`web/`) behind FastAPI (`src/ipl_sentiment_trading/ui/server.py`). Build once with `cd web && npm install && npm run build`; `ipl-ui` then serves uvicorn on **:8000** (static `web/dist` + `/api/matches`, `/api/analyze?match=&sentiment=&narrative=&bankroll=&trace=`).

## CLI
- `ipl-analyze list` → 71 frozen matches; gaps are 63, 66, 70.
- `ipl-analyze analyze 74 --sentiment vader` → fast (~3s). NOTE: with TYPESAFE_API_KEY set it is NOT fully offline — the Jev trade gate still fires (~3 real calls on match 74). Trace with `--decisions-jsonl <file>` to count.
- `ipl-analyze analyze 74 --sentiment jev --decisions-jsonl trace.jsonl` → ~41 real calls (38 intervals × 1 batched call + ~3 gate calls), ~3.5k questions, ~380k input tokens, ~5s. 0 fills expected (gate vetoes all proposals — designed behavior, not a bug).
- `ipl-analyze eval 74 --sentiment jev --trace eval.jsonl` → ~80 calls total (analyze + per-interval A/B Jev pass). Pass `--trace` explicitly: the `cost` report key is only emitted when the flag is given; default trace path `decisions.jsonl` lands in CWD.
- Jev outputs are nondeterministic — gate-veto counts and A/B sign-agreement vary a few %/calls between runs; question/call counts and input-token totals are structural and stable.

## Web UI
- `ipl-ui` → http://localhost:8000. Controls: match select, engine select (auto/jev/vader/none), Narrate + Trace checkboxes, Analyze button. Cursor moves via slider, clicking a chart (x-position → interval), or clicking a ledger row.
- Engine `auto` resolves to `jev` when the key is set (~41 real calls per run, ~5s — fast enough to leave on).
- Jev verdict chips only appear under `jev`/`auto-with-key` (vader shows "No interval verdict"); trace <details> table is per-request — usage counts are fresh each run.

## Known-good anchors (match 74 = SRH vs KKR Final)
- Winner KKR by 8 wickets; 38 intervals; ending equity 1000.00; fills 0.
- Signal reasons should be mostly `low-volume` and `edge-below-threshold` (~3 `ok` that the gate vetoes).
