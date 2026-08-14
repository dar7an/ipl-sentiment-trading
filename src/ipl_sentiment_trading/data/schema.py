"""Pydantic models for frozen `data/chunks` JSON. extra=ignore drops forecast_data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class MatchLoadError(ValueError):
    pass


class FrozenScore(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    runs: int = 0
    four: bool = False
    six: bool = False
    bye: int = 0
    leg_bye: int = 0
    is_wicket: bool = False
    ball: bool = False
    out: bool = False


class FrozenPlayer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    fullname: str = ""
    battingstyle: str | None = None
    bowlingstyle: str | None = None


class FrozenBall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ball: float | None = None
    updated_at: str | None = None
    id: int | None = None
    name: str = ""
    score: FrozenScore = Field(default_factory=FrozenScore)
    batsman: FrozenPlayer = Field(default_factory=FrozenPlayer)
    bowler: FrozenPlayer = Field(default_factory=FrozenPlayer)


class FrozenComment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: str | None = None
    comment: str = ""
    upvotes: int = 0


class FrozenPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    price: float


class FrozenOddsEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    last_update: str
    odds: list[FrozenPrice] = Field(default_factory=list)


class FrozenTeamInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    xi: list[str] = Field(default_factory=list)


class FrozenMatchInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    team1: FrozenTeamInfo
    team2: FrozenTeamInfo


class FrozenInningsBreakMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    first_innings_end: str | None = None
    second_innings_start: str | None = None


class FrozenChunk(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    start_time: str
    end_time: str
    is_pregame: bool = False
    is_innings_break: bool = False
    innings_break: FrozenInningsBreakMeta | None = None
    comments: list[FrozenComment] = Field(default_factory=list)
    odds: list[FrozenOddsEntry] = Field(default_factory=list)
    balls: list[FrozenBall] = Field(default_factory=list)


class FrozenMatchFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    match_info: FrozenMatchInfo
    chunks: list[FrozenChunk]

    @model_validator(mode="after")
    def _chunks_nonempty(self) -> FrozenMatchFile:
        if not self.chunks:
            raise ValueError("chunks must be a non-empty list")
        return self


class FrozenBallSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    round: str | None = None
    localteam_id: int | None = None
    visitorteam_id: int | None = None
    starting_at: str | None = None
    note: str | None = None
    venue_id: int | None = None
    toss_won_team_id: int | None = None
    winner_team_id: int | None = None


class FrozenBallsFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: FrozenBallSummary = Field(default_factory=FrozenBallSummary)
    balls: list[FrozenBall] = Field(default_factory=list)


def parse_match_file(payload: Any) -> FrozenMatchFile:
    try:
        return FrozenMatchFile.model_validate(payload)
    except ValidationError as exc:
        raise MatchLoadError(f"Not a frozen chunk-file schema: {exc}") from exc


def parse_balls_file(payload: Any) -> FrozenBallsFile:
    try:
        return FrozenBallsFile.model_validate(payload)
    except ValidationError as exc:
        raise MatchLoadError(f"Not a frozen balls-file schema: {exc}") from exc
