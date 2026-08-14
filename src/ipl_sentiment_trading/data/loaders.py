from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ipl_sentiment_trading.data.schema import (
    FrozenBallsFile,
    FrozenMatchFile,
    FrozenOddsEntry,
    MatchLoadError,
    parse_balls_file,
    parse_match_file,
)
from ipl_sentiment_trading.data.teams import abbreviation, canonicalize_team, winner_from_id
from ipl_sentiment_trading.data.timeutil import parse_corpus_datetime
from ipl_sentiment_trading.data.venues import venue_label

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


def find_data_root(explicit: Path | str | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if (path / "chunks").is_dir():
            return path
        if path.name == "data" and (path / "chunks").is_dir():
            return path
        raise FileNotFoundError(f"No chunks directory under {path}")
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data"
        if (candidate / "chunks").is_dir():
            return candidate
    cwd = Path.cwd() / "data"
    if (cwd / "chunks").is_dir():
        return cwd
    raise FileNotFoundError("Could not locate data/chunks. Set IPL_DATA_DIR.")


def available_match_ids(data_root: Path | str | None = None) -> list[int]:
    root = CorpusPaths(find_data_root(data_root))
    ids: list[int] = []
    for path in root.chunks.glob("*.json"):
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


@dataclass
class LoadedMatch:
    match_id: int
    team_a: str
    team_b: str
    team_a_abbr: str
    team_b_abbr: str
    xi_empty: bool
    frozen: FrozenMatchFile
    balls: FrozenBallsFile | None
    odds_timeline: list[FrozenOddsEntry]
    date: str | None
    venue: str | None
    round: str | None
    winner: str | None
    winner_note: str | None


def _timeline_from_chunks(match: FrozenMatchFile) -> list[FrozenOddsEntry]:
    out: list[FrozenOddsEntry] = []
    for chunk in match.chunks:
        out.extend(chunk.odds)
    return out


def _timeline_from_odds_file(path: Path) -> list[FrozenOddsEntry]:
    if not path.is_file():
        return []
    payload = _read_json(path)
    if not isinstance(payload, list):
        return []
    entries: list[FrozenOddsEntry] = []
    for item in payload:
        try:
            entries.append(FrozenOddsEntry.model_validate(item))
        except Exception:
            continue
    return entries


def _merge_odds(*series: list[FrozenOddsEntry]) -> list[FrozenOddsEntry]:
    seen: set[tuple[str, tuple[tuple[str, float], ...]]] = set()
    merged: list[FrozenOddsEntry] = []
    for group in series:
        for entry in group:
            key = (
                entry.last_update,
                tuple(sorted((p.name, float(p.price)) for p in entry.odds)),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
    def sort_key(entry: FrozenOddsEntry) -> tuple:
        try:
            return (parse_corpus_datetime(entry.last_update) or 0, entry.last_update)
        except ValueError:
            return (0, entry.last_update)

    return sorted(merged, key=sort_key)


def load_match(
    match_ref: str | int | Path,
    data_root: Path | str | None = None,
) -> LoadedMatch:
    root = find_data_root(data_root)
    paths = CorpusPaths(root)

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
    xi_empty = not frozen.match_info.team1.xi and not frozen.match_info.team2.xi

    balls: FrozenBallsFile | None = None
    balls_path = paths.balls / f"{match_id}.json"
    if balls_path.is_file():
        balls = parse_balls_file(_read_json(balls_path))

    odds_file = _timeline_from_odds_file(paths.odds / f"{match_id}.json")
    odds_timeline = _merge_odds(odds_file, _timeline_from_chunks(frozen))

    date = None
    venue = None
    round_name = None
    winner = None
    winner_note = None
    if balls is not None:
        date = balls.summary.starting_at
        venue = venue_label(balls.summary.venue_id)
        round_name = balls.summary.round
        winner_note = balls.summary.note
        winner = winner_from_id(balls.summary.winner_team_id, (team_a, team_b))

    return LoadedMatch(
        match_id=match_id,
        team_a=team_a,
        team_b=team_b,
        team_a_abbr=abbreviation(team_a),
        team_b_abbr=abbreviation(team_b),
        xi_empty=xi_empty,
        frozen=frozen,
        balls=balls,
        odds_timeline=odds_timeline,
        date=date,
        venue=venue,
        round=round_name,
        winner=winner,
        winner_note=winner_note,
    )


@dataclass(frozen=True)
class MatchCatalogRow:
    match_id: int
    label: str
    team_local: str | None
    team_visitor: str | None
    date: str | None
    venue: str | None
    round: str | None


def load_catalog(data_root: Path | str | None = None) -> list[MatchCatalogRow]:
    """Lightweight index from `data/balls` summaries (not the chunk comment blobs)."""
    from ipl_sentiment_trading.data.teams import ID_TO_CANONICAL

    root = CorpusPaths(find_data_root(data_root))
    rows: list[MatchCatalogRow] = []
    for match_id in available_match_ids(root.root):
        balls_path = root.balls / f"{match_id}.json"
        team_local = team_visitor = date = venue = round_name = None
        if balls_path.is_file():
            payload = _read_json(balls_path)
            if isinstance(payload, dict):
                summary = payload.get("summary") or {}
                team_local = ID_TO_CANONICAL.get(summary.get("localteam_id"))
                team_visitor = ID_TO_CANONICAL.get(summary.get("visitorteam_id"))
                date = summary.get("starting_at")
                venue = venue_label(summary.get("venue_id"))
                round_name = summary.get("round")
        vs = " vs ".join(t for t in (team_visitor, team_local) if t) or "Unknown fixture"
        round_bit = f"{round_name} · " if round_name else ""
        rows.append(
            MatchCatalogRow(
                match_id=match_id,
                label=f"{match_id} · {round_bit}{vs}",
                team_local=team_local,
                team_visitor=team_visitor,
                date=date,
                venue=venue,
                round=round_name,
            )
        )
    return rows
