---
name: testing-ipl-app
description: How to run and verify the ipl-sentiment-trading CLI and Streamlit UI end-to-end (Jev API calls, VADER offline mode, expected call counts, known quirks).
---

# Testing ipl-sentiment-trading

## Devin Secrets Needed
- `TYPESAFE_API_KEY` — enables Jev decide calls (sentiment engine + trade gate). Without it `auto` falls back to VADER.
- `GEMINI_API_KEY` — only needed for `--narrative` (Gemma narration); skippable for speed.

## Setup
- venv is `.venv` (editable install done). Binaries: `.venv/bin/ipl-analyze`, `.venv/bin/ipl-ui`.
- VADER needs `nltk.download('vader_lexicon')` once (blueprint initialize covers it).
- CLI defaults data dir via `<repo>/data`; UI `_catalog()` reads relative `data/chunks`, so always run `ipl-ui` from the repo root or match-picker labels break differently.

## CLI
- `ipl-analyze list` → 71 frozen matches; gaps are 63, 66, 70.
- `ipl-analyze analyze 74 --sentiment vader` → fast (~3s). NOTE: with TYPESAFE_API_KEY set it is NOT fully offline — the Jev trade gate still fires (~3 real calls on match 74). Trace with `--decisions-jsonl <file>` to count.
- `ipl-analyze analyze 74 --sentiment jev --decisions-jsonl trace.jsonl` → ~41 real calls (38 intervals × 1 batched call + ~3 gate calls), ~3.5k questions, ~380k input tokens, ~5s. 0 fills expected (gate vetoes all proposals — that is the designed behavior, not a bug).
- `ipl-analyze eval 74 --sentiment jev --trace eval.jsonl` → ~80 calls total (analyze + per-interval A/B Jev pass). Pass `--trace` explicitly: the `cost` report key is only emitted when the flag is given; default trace path `decisions.jsonl` lands in CWD.
- Jev outputs are nondeterministic — gate-veto counts and A/B sign-agreement vary a few %/calls between runs.

## Streamlit UI
- `.venv/bin/ipl-ui` → serves on :8501. With the API key set, the default `auto` engine runs the full ~41-call Jev analysis on page load (~5-10s) — this is fast enough to leave on.
- Per-match trace toggle writes `/tmp/jev_trace_{match_id}.jsonl` and **appends** — delete it before attributing call counts to a single run, and know the usage caption/trace table accumulate across engine switches.
- Replay slider + arrow keys move the interval cursor; Jev verdict chips only appear under `jev`/`auto-with-key` (vader shows "No interval verdict").

## Known-good anchors (match 74 = SRH vs KKR Final)
- Winner KKR by 8 wickets; 38 intervals; ending equity 1000.00; fills 0.
- Signal reasons should be mostly `low-volume` and `edge-below-threshold` (~3 `ok` that the gate vetoes).
