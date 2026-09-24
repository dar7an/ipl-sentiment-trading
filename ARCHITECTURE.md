# Architecture — the Jev-first paper book

This repository is a ground-up rewrite of the IPL 2024 sentiment-trading
project, redesigned so that **every fuzzy judgment in the pipeline is a typed
Jev decision**, while all arithmetic stays deterministic Python. It exists to
showcase what Jev (TypeSafe AI's System One decision model) does best.

## Thesis (unchanged)

For each frozen interval of an IPL 2024 match: market-implied probability
(proportional de-vig of decimal odds) is the prior; team-attributed Reddit
sentiment is log-odds evidence; `logit(p_view) = logit(p*) + α·1.5·tanh(s_a −
s_b)` with `α = n_eff/(n_eff+40)`; bet only when `|p_view − p*| ≥ 3%` and
effective attributed volume ≥ 20 (≥3 comments/team); quarter-Kelly stakes
capped at 5% equity and 15% total exposure; fills mark to `p*` and settle on
the frozen winner. Fees and slippage are 0.

**Data is frozen and immutable**: never modify anything under `data/`,
`archive/`, or `examples/`.

## The two-model split

- **Jev** (`api.typesafe.ai/v1/systemone`, model `jev-latest`) makes every
  small typed judgment: relevance gates, team attribution, bullishness
  scores, regime classification, trade guardrails, narrator routing, context
  compaction. Answers are `choice`/`score`/`noul` with calibrated
  probabilities — code branches on them directly.
- **Gemma 4** (via Gemini API, `gemma-4-26b-a4b-it` default /
  `gemma-4-31b-it` for high-drama intervals; or any OpenAI-compatible
  endpoint via `NARRATIVE_BASE_URL`) writes optional human prose. It never
  decides anything — it narrates what Jev decided.

If an agent wants a "smart" string parsed, a regex over language, or an
LLM-prose judgment → that is a Jev question. If it's arithmetic → Python.

## Jev API contract (verified)

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
{"model": "jev-latest", "state": "<string>", "questions": {...}}
→ {"model": "...", "answers": {...}, "usage": {"input_tokens": N, "output_tokens": N}}
```

Question types (all have `instructions: str`):
- `choice`: + `criteria: {key: description}` → answer `{type, choice, confidence, probabilities{key:p}}`
- `score`: + `criteria: [level descriptions low→high]` (2–10 levels) → `{type, score(fractional), confidence, legend, probabilities{level_idx:p}}`
- `noul`: instructions only → `{type, noul: 0..1}`

Many questions share one `state` in a single call. Env vars:
`TYPESAFE_API_KEY` (primary) or `JEV_API_KEY` (metered proxy;
`JEV_BASE_URL=https://jevtypesafeai.com/api/v1/decide`), `JEV_MODEL`
(default `jev-latest`), `JEV_BASE_URL` (override official endpoint).

## Package map — `src/ipl_sentiment_trading/`

| Path | Owner | Contents |
|---|---|---|
| `domain/models.py` | orchestrator | shared pydantic contract (done) |
| `jev/` | A1 | `types.py` `client.py` `questions.py` `cache.py` `trace.py` |
| `corpus/` `cricket/` `market/` | A2 | frozen-data loaders, team normalization, legal-ball cricket state, de-vig odds |
| `sentiment/` | A3 | `candidates.py` `jev_engine.py` `vader.py` `lexicon.py` `aggregate.py` |
| `signal/` `policy/` `ledger/` | A4 | log-odds view, gates+Kelly, paper book |
| `narrate/` | A5 | `gemma.py` `router.py` `context.py` |
| `pipeline/` `cli.py` `__main__.py` `config.py` `ui/` | A6 | orchestration, argparse CLI, Streamlit app |
| `eval/` | A7 | `ab.py` `report.py` |

Ownership is exclusive: an agent may create/modify ONLY the paths listed for
it. Cross-module needs are satisfied by the interfaces below — never by
editing another module or `domain/models.py`, `pyproject.toml`, `README.md`,
`.env.example` (report needed deps in the structured output instead).

## Interface contracts

### A1 — `jev/` (no deps)

`jev/types.py`:
```python
class BaseQ(BaseModel): type: str; instructions: str
class ChoiceQ(BaseQ): type: Literal["choice"]="choice"; criteria: dict[str,str]
class ScoreQ(BaseQ):  type: Literal["score"]="score";   criteria: list[str]  # 2..10
class NoulQ(BaseQ):   type: Literal["noul"]="noul"
Question = ChoiceQ | ScoreQ | NoulQ
class ChoiceA(BaseModel): type: Literal["choice"]; choice: str; confidence: float=0; probabilities: dict[str,float]={}
class ScoreA(BaseModel):  type: Literal["score"];  score: float; confidence: float=0; probabilities: dict[str,float]={}; legend: dict[str,str]={}
class NoulA(BaseModel):   type: Literal["noul"];   noul: float
Answer = Annotated[ChoiceA|ScoreA|NoulA, Field(discriminator="type")]
class Usage(BaseModel): input_tokens: int=0; output_tokens: int=0
class DecideResult(BaseModel): answers: dict[str, Answer]; usage: Usage; model: str=""
```

`jev/client.py`:
```python
DecideFn = Callable[[str, dict[str, Question]], DecideResult]  # the injected seam everywhere
class JevError(RuntimeError): ...
class DecideClient:
    def __init__(self, api_key: str|None=None, base_url: str|None=None,
                 model: str="jev-latest", cache=None, tracer=None,
                 timeout: float=30.0, max_retries: int=4): ...
    def decide(self, state: str, questions: dict[str, Question]) -> DecideResult
```
- key resolution order: arg → `TYPESAFE_API_KEY` → `JEV_API_KEY`; base_url arg → `JEV_BASE_URL` → official default (if `JEV_API_KEY` is a `jv_live_*` key and no base_url given, default to the metered proxy `https://jevtypesafeai.com/api/v1/decide`).
- POST JSON `{"model": model, "state": state, "questions": {k: q.model_dump()}}`; httpx; retry on 429/5xx/transport errors with exponential backoff+jitter; raise `JevError` with status on non-retryable.
- `cache`: object with `.get(key)->DecideResult|None` / `.set(key, result)`; key = sha256 of `model|state|canonical question json`. Cache hits must not hit the network or the tracer's API counters (but DO log a trace entry with `cache_hit: true`).
- `tracer`: `.record(TraceEntry)`.

`jev/cache.py`: `MemoryCache`, `JsonlCache(path)` (append-only JSONL keyed store; tolerant of corruption — skip bad lines). `jev/trace.py`: `TraceEntry` (ts, latency_ms, n_questions, usage, cache_hit, answers_digest) and `JsonlTracer(path)` which also tracks running totals `totals() -> dict`.

`jev/questions.py` — domain question builders (the showcase surface):
```python
def comment_questions(comments: list[Comment], team_a: TeamRef, team_b: TeamRef) -> dict[str, Question]
    # per candidate i: f"c{i}_relevant" noul (about this match/cricket, not spam/off-topic),
    # f"c{i}_team" choice {team_a|team_b|neutral} (side it supports/praises/mocks; neutral for
    #   general reactions, questions, abuse not aimed at a side),
    # f"c{i}_bullish" score 1..5 (how bullish on that side's chances right now)
def interval_questions(team_a: TeamRef, team_b: TeamRef) -> dict[str, Question]
    # "regime" choice {one_sided|tense|swing|dead}; "signal_quality" score 1..5;
    # "odds_stale" noul; "narrate" noul
def trade_gate_question() -> dict[str, Question]   # {"gate": noul — is the edge genuine signal?}
def route_question() -> dict[str, Question]        # {"drama": score 1..5}
def compaction_question() -> dict[str, Question]   # per-fact choice {keep|trim|drop}
```

### A2 — corpus / cricket / market (no deps beyond domain)

`corpus/schema.py`: raw pydantic for the three JSON shapes (do NOT mutate raw dicts; `forecast_data`, `winner_team_id`, `note` are settlement-only).
`corpus/teams.py`: `canonical_name(raw: str) -> str`, `abbreviation(name) -> str`, `TEAM_ALIASES` incl. "Royal Challengers Bangalore"→"Royal Challengers Bengaluru"→RCB; all 10 IPL 2024 franchises.
`corpus/loader.py`:
```python
CORPUS_GAPS = [63, 66, 70]
class MissingMatchError(FileNotFoundError): ...
def data_root(explicit: Path|None=None) -> Path   # arg → $IPL_DATA_DIR → <repo>/data
def available_match_ids(root: Path|None=None) -> list[int]
def load_match(match: int|str|Path, root: Path|None=None) -> CorpusMatch
    # accepts match id or path to chunks json; maps chunk list → Interval list;
    # parse "%Y-%m-%d %I:%M:%S %p" (+ optional " IST"); odds → OddsSnapshot (source_index=i)
```
`cricket/legal.py` (as built): `is_wide/is_no_ball/is_legal_delivery/is_dot/is_boundary_ball/run_rate/pct/total_runs` on `RawBallScore`; `total_runs = runs + bye + leg_bye` (score.runs already carries wide/no-ball penalties).
`cricket/state.py` (as built): `CricketTracker(team_a, team_b)` — `note_interval_flags(is_innings_break=...)`, `apply_balls(balls) -> WindowStats`, `snapshot(is_pregame=..., is_innings_break=...) -> CricketState`, `player_team` surname→team map for narrative attribution. **Feeds the complete `CorpusMatch.balls` feed**, not chunk-embedded subsets — the pipeline feeds balls-file balls whose `updated_at` falls in `(prev_interval_end, interval_end]` so cumulative state never misses balls between chunk boundaries. Legal balls exclude wides/no-balls; dot% counts legal 0-total-run balls incl. wickets; partnership (all runs incl. extras) persists until a wicket; innings switch on batting-team change or an innings-break flag; never read `forecast_data`.
`market/odds.py` (as built): `implied_probability`, `two_way_market`, `quote_for_teams`, `latest_snapshot_as_of`, `quote_as_of(odds, end, team_a, team_b, prev_snapshot=None)` — last snapshot with `last_update <= end` (carry-forward flag when it's the same snapshot as the previous interval), `p_raw = 1/decimal`, `overround = Σp_raw − 1`, `p_fair = p_raw/Σ`.

### A3 — `sentiment/` (deps: domain, corpus.teams, jev.types — inject `DecideFn`)

`candidates.py`: `select_candidates(comments, k=30) -> list[tuple[int, Comment]]` — dedupe identical text; keep top `k` by `upvotes` then time-even fill; truncate text to 280 chars.
`jev_engine.py`:
```python
class JevSentimentEngine:
    def __init__(self, decide: DecideFn, team_a: TeamRef, team_b: TeamRef,
                 max_candidates: int=30): ...
    def analyze(self, interval: Interval) -> SentimentSnapshot
    # one Jev call: state = numbered candidate comments (original indices kept);
    # questions = comment_questions(...) + interval_questions(...);
    # CommentVerdicts + IntervalVerdict → aggregate.py → SentimentSnapshot(source="jev")
```
`aggregate.py`: probability-weighted aggregation — per comment, `w = relevant × (1+upvotes)^0.5`; `s_a = Σ w·p(team_a)·(bullish/5−0.5)·2` etc.; bucket `effective_volume = Σ w·p(team)`; `volume = count(relevant>0.5)`. Match-level bucket aggregates neutrals. Expose `signal_strength(snap) -> (s_a, s_b, n_eff)`.
`vader.py` + `lexicon.py`: port the VADER+cricket-lexicon baseline from git history (`git show a6e0a60^:src/ipl_sentiment_trading/sentiment/...` or earlier commits) producing the same `SentimentSnapshot` (source="vader", no verdicts) — it is the offline fallback and A/B baseline.

### A4 — signal / policy / ledger (deps: domain only; inject DecideFn for the gate)

`signal/view.py`: `compute_view(quote, snapshot, min_edge=0.03, min_eff_volume=20, min_comments=3) -> Signal` — exact thesis math above; reason strings: `"no-odds"`, `"low-volume"`, `"edge-below-threshold"`, `"ok"`; `p_sent_a = 0.5 + 0.5·tanh(s_a−s_b)` reported for transparency.
`policy/decide.py`:
```python
def propose_fill(signal, quote, ledger, params, gate: DecideFn|None=None) -> Fill|None
```
- if `signal.side` and quote: stake = `min(0.25·kelly, 0.05·equity, cash)`; no same-side pyramid; exposure ≤ 15%·bankroll. When `gate` provided: build a compact `state` (teams, p*, p_view, edge, sentiment volumes, regime, signal_quality) → `trade_gate_question()` → `TradeGate(p_genuine=answers["gate"].noul, approved=noul≥0.5)`; vetoed fills return `Fill` with `reason="jev-veto"`? NO — vetoed proposals return None and are logged via the gate result in `live_features["gate"]` by the pipeline. (Pipeline reads `propose_fill` returning `(Fill|None, TradeGate|None)` — return a tuple.)
`ledger/book.py`: `class PaperBook(starting_bankroll)` — `apply_fill(fill)`, `mark(quote)` → `LedgerSnapshot` (exposure = Σ stake·p*·decimal for open fills, equity = cash + exposure), `settle(winner: str)` — settles remaining opens on the frozen winner; tracks `realized_pnl`, `max_drawdown`.

### A5 — `narrate/` (deps: domain; inject DecideFn)

`gemma.py`:
```python
class GemmaNarrator:
    def __init__(self, api_key=None, base_url=None, model_flash="gemma-4-26b-a4b-it",
                 model_pro="gemma-4-31b-it"): ...
    # Gemini API via google-genai SDK when GEMINI_API_KEY/GOOGLE_API_KEY set;
    # else OpenAI-compatible chat-completions at NARRATIVE_BASE_URL (local Gemma 4);
    # narrate(interval_ctx: str, model: str) -> str
```
`router.py`: `route(decide: DecideFn, interval_ctx: str) -> NarratorRoute` — `route_question()` drama score ≥3.5 → pro model else flash; also returns reason. `context.py`: `compact(decide, facts: list[str], keep=8) -> list[str]` — one call, per-fact `choice{keep|trim|drop}`; trim → first sentence.

### A6 — pipeline / cli / ui / config (deps: all, read-only imports)

`pipeline/analyze.py`: `analyze_match(match, data_root=None, params=TradingParams(), sentiment="auto", narrate=False, sample_k=30, decide: DecideFn|None=None) -> AnalysisResult` — assemble CorpusMatch → per interval: cricket state+window, market quote, sentiment (engine from `sentiment`: "jev" if client ok, "vader" fallback, "none" — log choice), signal, propose_fill (+gate via decide), book.mark/settle at end, optional narrator (only when `interval_verdict.narrate ≥ 0.5` and routed), collect `jev_usage` from tracer totals. `live_features` must provably exclude winner/forecast/narrative text — keep a `test_lookahead.py` invariant (pipeline must not read `summary.winner` until settle).
`config.py`: `TradingParams(starting_bankroll=1000, edge_threshold=0.03, min_eff_volume=20, min_comments_per_team=3, kelly_fraction=0.25, max_stake_pct=0.05, max_exposure_pct=0.15)` + env helpers `resolve_jev_client()` / `resolve_narrator()` returning `None` when unconfigured (never raise for missing keys).
`cli.py`: `ipl-analyze {list,analyze <id|path>,eval <id>}` flags `-o/--output`, `--format {json,md}`, `--narrative`, `--bankroll`, `--sentiment {auto,jev,vader,none}`, `--sample-k N`, `--trace PATH` (write decisions.jsonl), keep legacy positional forms working (see git history for exact behavior); `__main__.py` = cli.main. `ipl-ui` launches streamlit.
`ui/app.py`: match picker; Plotly equity curve, p_view vs p*, sentiment streams, fill markers; **"Jev decisions" panel** — table of every traced decision (question→answer→confidence→latency→tokens) and a running token/cost ticker.

### A7 — `eval/` (deps: domain, sentiment, signal, market; inject DecideFn)

`eval/ab.py`: `compare_engines(match, decide) -> dict` — run Jev+VADER per interval: mean|Δ| sentiment gap, rank correlation, share of intervals where sign(s_a−s_b) agrees.
`eval/report.py`: `cost_report(trace_path) -> dict` (calls, questions, input_tokens, p50/p95 latency, cache-hit rate, gate vetoes, narrator routes) and `brier_report(result: AnalysisResult) -> dict` (Brier of p_view and p* vs frozen winner — eval-only use of winner).

## Testing rules (all agents)

- `pytest` must pass **fully offline**: never call Jev/Gemini in tests — inject a fake `DecideFn`/`transport`.
- Use the real corpus where it helps (`data/chunks/74.json` etc. are in-repo).
- Style: pydantic v2 models, `from __future__ import annotations`, no `Any` leaks unless the contract says so, minimal comments (none narrating changes).
- Run: `python -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/pytest tests/test_<yours>.py` (or `uv sync --extra dev && uv run pytest` if `uv` exists).

## Definition of done (whole repo)

- `ipl-analyze list` and `ipl-analyze analyze 74` run fully offline (vader fallback).
- With `TYPESAFE_API_KEY`: Jev engine produces verdicts + `decisions.jsonl` trace.
- With `GEMINI_API_KEY` + `--narrative`: Gemma 4 prose on Jev-selected intervals.
- `ipl-analyze eval 74` writes an A/B + cost + Brier report.
- README documents the Jev usage map with measured latency/cost.
