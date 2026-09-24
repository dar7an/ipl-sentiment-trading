"""Load the frozen IPL 2024 corpus into domain types."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ipl_sentiment_trading.corpus.schema import (
    FrozenBallsFile,
    FrozenMatchFile,
    FrozenOddsEntry,
    MatchLoadError,
    parse_balls_file,
    parse_match_file,
)
from ipl_sentiment_trading.corpus.teams import (
    canonicalize_team,
    team_ref,
    winner_from_id,
)
from ipl_sentiment_trading.corpus.timeutil import parse_corpus_datetime
from ipl_sentiment_trading.corpus.venues import venue_label
from ipl_sentiment_trading.domain.models import (
    Comment,
    CorpusMatch,
    Interval,
    MatchSummary,
    OddsSnapshot,
    Price,
    RawBall,
    RawBallScore,
)

CORPUS_GAPS = (63, 66, 70)


class MissingMatchError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class CorpusPaths:
    root: Path

    @property
    def chunks(self) -> Path:
        return self.root / "chunks"

    @property
    def balls(self) -> Path:
        return self.root / "balls"

    @property
    def odds(self) -> Path:
        return self.root / "odds"


def data_root(explicit: Path | str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if (path / "chunks").is_dir():
            return path
        raise FileNotFoundError(f"No chunks directory under {path}")
    import os

    env = os.getenv("IPL_DATA_DIR")
    if env and (Path(env) / "chunks").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data"
        if (candidate / "chunks").is_dir():
            return candidate
    cwd = Path.cwd() / "data"
    if (cwd / "chunks").is_dir():
        return cwd
    raise FileNotFoundError("Could not locate data/chunks. Set IPL_DATA_DIR.")


def available_match_ids(root: Path | str | None = None) -> list[int]:
    paths = CorpusPaths(data_root(root))
    ids: list[int] = []
    for path in paths.chunks.glob("*.json"):
        try:
            ids.append(int(path.stem))
        except ValueError:
            continue
    return sorted(ids)


def _read_json(path: Path) -> object:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise MatchLoadError(f"Invalid JSON in {path}: {exc}") from exc


def _to_ball(ball) -> RawBall:
    score = ball.score
    return RawBall(
        ball=ball.ball or 0.0,
        updated_at=parse_corpus_datetime(ball.updated_at),
        name=ball.name or "",
        score=RawBallScore(
            name=score.name or "",
            runs=score.runs,
            four=score.four,
            six=score.six,
            bye=score.bye,
            leg_bye=score.leg_bye,
            is_wicket=score.is_wicket,
            ball=score.ball,
            out=score.out,
        ),
        batsman=ball.batsman.model_dump(mode="json") if ball.batsman else None,
        bowler=ball.bowler.model_dump(mode="json") if ball.bowler else None,
    )


def _snapshot_from_entry(entry: FrozenOddsEntry, source_index: int) -> OddsSnapshot | None:
    stamp = parse_corpus_datetime(entry.last_update)
    if stamp is None or not entry.odds:
        return None
    prices = [
        Price(
            team=canonicalize_team(p.name) or p.name,
            decimal_odds=float(p.price),
        )
        for p in entry.odds
    ]
    return OddsSnapshot(last_update=stamp, prices=prices, source_index=source_index)


def _odds_timeline(frozen: FrozenMatchFile, odds_path: Path) -> list[OddsSnapshot]:
    entries: list[FrozenOddsEntry] = []
    payload = _read_json(odds_path) if odds_path.is_file() else []
    if isinstance(payload, list):
        for item in payload:
            try:
                entries.append(FrozenOddsEntry.model_validate(item))
            except ValueError:
                continue
    for chunk in frozen.chunks:
        entries.extend(chunk.odds)
    seen: set[tuple[str, tuple[tuple[str, float], ...]]] = set()
    snapshots: list[OddsSnapshot] = []
    for idx, entry in enumerate(entries):
        key = (
            entry.last_update,
            tuple(sorted((p.name, float(p.price)) for p in entry.odds)),
        )
        if key in seen:
            continue
        seen.add(key)
        snap = _snapshot_from_entry(entry, idx)
        if snap is not None:
            snapshots.append(snap)
    snapshots.sort(key=lambda s: (s.last_update, s.source_index))
    return snapshots


def load_match(
    match_ref: str | int | Path,
    root: Path | str | None = None,
) -> CorpusMatch:
    paths = CorpusPaths(data_root(root))

    ref_path = Path(str(match_ref))
    if ref_path.suffix == ".json" and ref_path.is_file():
        chunk_path = ref_path
        try:
            match_id = int(chunk_path.stem)
        except ValueError:
            match_id = 0
    else:
        try:
            match_id = int(match_ref)
        except (TypeError, ValueError) as exc:
            raise MatchLoadError(f"Not a match id or chunk file: {match_ref!r}") from exc
        if match_id in CORPUS_GAPS:
            raise MissingMatchError(
                f"Match {match_id} is not in the frozen 2024 corpus "
                f"(gaps: {', '.join(str(g) for g in CORPUS_GAPS)})."
            )
        chunk_path = paths.chunks / f"{match_id}.json"
        if not chunk_path.is_file():
            raise MissingMatchError(f"No chunk file for match {match_id} at {chunk_path}")

    frozen = parse_match_file(_read_json(chunk_path))
    team_a = canonicalize_team(frozen.match_info.team1.name) or frozen.match_info.team1.name
    team_b = canonicalize_team(frozen.match_info.team2.name) or frozen.match_info.team2.name

    balls_file: FrozenBallsFile | None = None
    balls_path = paths.balls / f"{match_id}.json"
    if balls_path.is_file():
        balls_file = parse_balls_file(_read_json(balls_path))

    date = venue = round_name = winner = winner_note = None
    if balls_file is not None:
        date = balls_file.summary.starting_at
        venue = venue_label(balls_file.summary.venue_id)
        round_name = balls_file.summary.round
        winner_note = balls_file.summary.note
        winner = winner_from_id(balls_file.summary.winner_team_id, (team_a, team_b))

    intervals: list[Interval] = []
    for chunk in frozen.chunks:
        start = parse_corpus_datetime(chunk.start_time)
        end = parse_corpus_datetime(chunk.end_time)
        if start is None or end is None:
            raise MatchLoadError(f"Chunk {chunk.name} missing timestamps")
        intervals.append(
            Interval(
                name=chunk.name,
                start_time=start,
                end_time=end,
                is_pregame=chunk.is_pregame,
                is_innings_break=chunk.is_innings_break,
                comments=[
                    Comment(
                        timestamp=parse_corpus_datetime(c.timestamp) or start,
                        text=c.comment,
                        upvotes=c.upvotes,
                    )
                    for c in chunk.comments
                ],
                balls=[_to_ball(b) for b in chunk.balls],
            )
        )

    return CorpusMatch(
        summary=MatchSummary(
            match_id=match_id,
            team_a=team_ref(team_a),
            team_b=team_ref(team_b),
            round=round_name,
            date=date,
            venue=venue,
            winner=winner,
            winner_note=winner_note,
            missing_xi=not frozen.match_info.team1.xi and not frozen.match_info.team2.xi,
        ),
        intervals=intervals,
        odds=_odds_timeline(frozen, paths.odds / f"{match_id}.json"),
        balls=[_to_ball(b) for b in (balls_file.balls if balls_file else [])],
    )
