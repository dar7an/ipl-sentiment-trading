# IPL 2024 paper book

Offline research demo: for each frozen 5-minute-ish interval of an IPL 2024 match, the app builds cricket state, de-vigged FanDuel probabilities, team-attributed Reddit sentiment, and a path-dependent paper ledger.

It is **not** live betting, not a broker, and not a Gemini narrator. The 2024 JSON dumps are the product. Optional LLM prose is a sidecar.

The previous class project lived in `examples/74.md` as Gemini paragraphs. That file is an artifact, not the current output.

## Install

Python 3.11+ (developed on 3.14). `pyproject.toml` is the only pin file.

```bash
uv sync --extra dev
# or: python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

First sentiment run downloads NLTK's VADER lexicon.

Copy `.env.example` only if you want the narrative sidecar. The CLI and UI run with no env file.

## Run

```bash
# paper book for the final (match 74), no API key
uv run python -m ipl_sentiment_trading analyze 74
uv run python -m ipl_sentiment_trading analyze 74 -o analysis-74.json
uv run python -m ipl_sentiment_trading analyze 74 -o analysis-74.md --format md

uv run python -m ipl_sentiment_trading list

# UI
uv run ipl-ui
# or: uv run streamlit run src/ipl_sentiment_trading/ui/app.py
```

Legacy: `ipl-analyze 74 out.md` still works and now writes the paper book, not Gemini copy.

## What the numbers are

**Odds.** `p_raw = 1/decimal`. Overround = `sum(p_raw) - 1`. Fair `p* = p_raw / sum(p_raw)` (proportional de-vig — juice scaled off both sides equally; not Shin). Each interval uses the last snapshot with `last_update` ≤ interval end, including carry-forward when later chunks have no prints. Decimal **1.01 is not implied 1.00**.

**Sentiment.** VADER plus a cricket lexicon (six, golden duck, wicket maiden, …). Comments are attributed to a team via names, abbreviations, nicknames, and players seen so far. Interval signal is two team means + volumes, not one match blob.

**View and stake.** Market `p*` is the prior. Sentiment is log-odds evidence: `logit(p_view) = logit(p*) + α · 1.5 · tanh(s_a − s_b)`, `α = n / (n + 40)`. Mixing `p*` with a 50/50-centered tanh would call every longshot a 3%+ edge; this update does not. Bet only if `|p_view − p*| ≥ 3%` and attributed volume ≥ 20 with at least 3 comments per team. Back the favored side at as-of-t decimal odds. Stake is `min(0.25 Kelly, 5% of equity)`, cash-capped. Same-side fills are not pyramided; exposure is capped at 15% of starting bankroll. **Fees and slippage are 0.**

**Marks.** Open fills mark to current `p*`: value = `stake × p*_side × decimal_fill`. Remaining positions settle on the frozen winner **after** the last interval's live decision. Live features never include the winner, `forecast_data`, or prior LLM text.

**Cricket.** Legal balls exclude wides and no-balls. Dot % includes wicket balls with 0 runs. Partnerships persist across intervals until a wicket. RR is 0 when legal balls = 0. `boundary_ball_pct` is ball frequency; `boundary_run_share` is run share. Innings changes use batting-team switches and `is_innings_break`, not `ball == 6.0`. Ball clocks are Sportmonks `updated_at`.

## Corpus caveats

- Frozen IPL 2024. Do not re-scrape. Do not rewrite `data/chunks`, `data/balls`, or `data/odds`.
- 71 matches. **63, 66, 70 are missing.**
- Playing XI is empty on every match — the UI omits it.
- Odds dumps say “Royal Challengers Bangalore”; chunks say “Bengaluru”. Names are normalized.
- `archive/data_collection/` is dead scraping code with a different chunk schema. Not runtime.

## Narrative sidecar (optional)

Off unless `--narrative` / UI toggle **and** credentials:

```bash
export GEMINI_API_KEY=...          # or GOOGLE_API_KEY
export NARRATIVE_MODEL=gemini-3.5-flash-lite
uv run python -m ipl_sentiment_trading analyze 74 --narrative
```

Local Gemma 4 (or any OpenAI-compatible chat endpoint) — no GPU required in this repo:

```bash
export NARRATIVE_BASE_URL=http://127.0.0.1:8080/v1
export NARRATIVE_MODEL=gemma-4-26b-it   # whatever your server expects
```

Uses `google-genai`, not deprecated `google-generativeai`. Google is imported only when narrative is actually constructed.

## Tests

```bash
uv run pytest
```
