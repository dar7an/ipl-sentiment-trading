# ipl-sentiment-trading — a Jev showcase

A replayed IPL 2024 paper book driven end-to-end by **Jev**, TypeSafe's System
One decision model. Every fuzzy judgment a trading pipeline needs — reading a
crowd, grading a signal, vetoing a bet, deciding what to say and how to say it —
is a typed Jev decision (`choice` / `score` / `noul`) over a shared `state`,
recorded in an auditable trace. All arithmetic — odds de-vigging, the log-odds
view model, Kelly sizing, mark-to-market, settlement — is deterministic Python.

The original thesis is preserved: Reddit match-thread sentiment vs. FanDuel
implied probability, over the 2024 season's frozen 5-minute chunks. What's new
is *who makes the judgments* — Jev, not regexes — and that every judgment is
inspectable in `decisions.jsonl`.

## Why Jev (and where it fits)

Jev is a small decision model: you post a `state` string plus a map of typed
`questions`, and it answers all of them in one call with calibrated
probabilities (`noul` for booleans, `choice`+`probabilities` for categoricals,
`score`+`probabilities` for rankings). Three properties shaped this design:

1. **Questions share the state prefix.** 94 judgments about one interval cost
   ~10k input tokens *once*, not 94 times — so the design batches *every*
   per-comment question of an interval into a single `decide` call.
2. **It's fast and cheap** — measured p50 ≈ 100 ms, ~10k tokens/call (≈ $0.01
   at $1/Mtok) — so a per-interval event loop calling it ~2× per interval is
   practical, and every call can be traced.
3. **It doesn't do arithmetic.** Win probabilities, Kelly stakes, de-vig —
   numbers come from deterministic code; Jev only decides things that are
   genuinely judgment.

## The Jev usage map

| # | Decision point | Question type | State | Purpose |
|---|----------------|---------------|-------|---------|
| 1 | `comment_questions` per interval | 3 × per candidate comment (`noul` relevant, `choice` team_a/team_b/neutral, `score` bullishness 0–5) | Comments + cricket + market context | Replaces the lexicon: typed, calibrated sentiment attributed to teams |
| 2 | `interval_questions` | `choice` regime, `score` quality, `noul` odds-stale, `noul` narrate | Same state | Interval-level verdicts that gate downstream steps |
| 3 | `trade_gate_question` | `noul` (is the edge genuine?) | Proposal prose: side, decimal, edge, sizes, cricket state | Last-line guardrail before every paper fill |
| 4 | `route_question` | `score` drama 1–5 | Compact interval card | Routes narration between `gemma-4-26b-a4b-it` and `gemma-4-31b-it` |
| 5 | `compaction_questions` | `noul` keep per fact | Narrator memory | Trims the narrator's context when it outgrows budget |

Plus the plumbing: `DecideClient` (official `api.typesafe.ai/v1/systemone`
or the metered proxy, retries + JSONL cache), `JsonlTracer` (one trace row per
call), and `JevSentimentEngine` (the big batched call).

## Pipeline

```
match chunk → CricketTracker (balls, wickets, windows)
            → quote_as_of (de-vigged FanDuel; carry-forward staleness flag)
            → JevSentimentEngine (one decide call: N×3 comment + 4 interval questions)
            → compute_view (deterministic log-odds + shrinkage; needs ≥3 comments/team,
              |edge| ≥ 3%, effective volume ≥ 20)
            → propose_fill (Kelly stake caps, exposure cap, then the Jev gate)
            → PaperBook (mark / settle)
            → GemmaNarrator (if verdict says narrate; Jev routes the model)
```

`live_features` per interval carry everything needed to learn offline; a
lookahead guard refuses any feature derived from `forecast_data`, `winner`, or
`note` fields.

## Measured on the IPL 2024 final (match 74, SRH vs KKR)

From `ipl-analyze analyze 74 --sentiment jev --narrative --decisions-jsonl`:

| Metric | Value |
|--------|-------|
| decide calls | 82 (81 API + 1 cache hit) |
| typed questions answered | 3,648 |
| input tokens / est. cost | 401,903 / ≈ $0.40 @ $1/Mtok |
| latency p50 / p95 | 98 ms / 155 ms |
| Jev gate vetoes | 3 of 3 proposed fills (all below the 0.5 bar: 0.40, 0.39, 0.45) |
| intervals narrated by Gemma | 30 of 38 |

Match 74 was a KKR blowout, priced correctly. Jev's read of the crowd agreed —
it attributed almost everything to KKR and vetoed every marginal SRH-lean
proposal. **Zero fills, flat book, and the trace shows exactly why.** That is
the point: the guardrail is a decision model, so its "no" is a calibrated
probability you can inspect, not a threshold you can't.

A/B vs. the VADER baseline (`ipl-analyze eval 74`): sign agreement 45–53%
across runs (Jev is nondeterministic), rank correlation ~0.1 — Jev is far more discriminating about what a comment is
actually saying (its mean per-interval sentiment gap was +0.9 pts vs. VADER's
−7.6 pts, matching the KKR-dominant crowd). Brier on this match: view 0.045 vs
market 0.040 — the sentiment overlay added noise on a game the market already
had right; the corpus covers more than one match.

Sample Gemma narration (routed): *"Sunrisers Hyderabad's collapse intensifies
as the seventh wicket falls, leaving them entirely at KKR's mercy in this
one-sided final."*

## Quickstart

Python 3.11+.

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                                  # 36 tests, fully offline
.venv/bin/ipl-analyze list                        # corpus matches
.venv/bin/ipl-analyze analyze 74 --sentiment vader # offline sentiment; the Jev gate still fires if TYPESAFE_API_KEY is set

export TYPESAFE_API_KEY=...   # Jev (or JEV_API_KEY for the metered proxy)
.venv/bin/ipl-analyze analyze 74 --sentiment jev --decisions-jsonl trace.jsonl

export GEMINI_API_KEY=...     # Gemma 4 narrator
.venv/bin/ipl-analyze analyze 74 --sentiment jev --narrative
.venv/bin/ipl-analyze eval 74 --sentiment jev --trace trace.jsonl  # A/B + cost + Brier
cd web && npm install && npm run build          # build the React+StyleX UI once
.venv/bin/ipl-ui              # serves it + the JSON API on :8000
```

`.env.example` documents every key. With no keys, everything still runs — the
sentiment engine falls back to VADER and the narrator is skipped.

## Layout

```
src/ipl_sentiment_trading/
  corpus/    match/balls/odds/comments loading, teams, venues, timeutils
  cricket/   legal scoring rules + CricketTracker (innings state, windows)
  market/    de-vig, quotes, carry-forward staleness
  sentiment/ VADER baseline, candidate sampling, JevSentimentEngine, aggregation
  signal/    log-odds view + effective-volume shrinkage
  policy/    proposal construction + Jev trade gate
  ledger/    path-dependent paper book (fills, MTM, settlement, drawdown)
  narrate/   Gemma 4 narrator w/ Jev drama routing + memory compaction
  jev/       DecideClient, question builders, JSONL cache + tracer
  pipeline/  analyze_match orchestration + leak-guarded live features
  eval/      VADER A/B, Brier report, cost report
  ui/        FastAPI server (JSON API + static host for the React UI)
data/        frozen IPL 2024 corpus (chunks, balls, odds, comments) — read-only
web/         React + StyleX single-page UI (Vite; builds to web/dist)
ARCHITECTURE.md   design spec and the swarm's build plan
```

Not live betting, not a broker, not financial advice.
