"""Typed contract for the Jev decision API. See ARCHITECTURE.md."""

from __future__ import annotations

from typing import Annotated, Callable, Literal

from pydantic import BaseModel, Field


class BaseQ(BaseModel):
    type: str
    instructions: str


class ChoiceQ(BaseQ):
    type: Literal["choice"] = "choice"
    criteria: dict[str, str]  # option key -> what it means


class ScoreQ(BaseQ):
    type: Literal["score"] = "score"
    criteria: list[str]  # level descriptions, low -> high (2..10)


class NoulQ(BaseQ):
    type: Literal["noul"] = "noul"


Question = ChoiceQ | ScoreQ | NoulQ


class ChoiceA(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: float = 0.0
    probabilities: dict[str, float] = Field(default_factory=dict)


class ScoreA(BaseModel):
    type: Literal["score"]
    score: float
    confidence: float = 0.0
    probabilities: dict[str, float] = Field(default_factory=dict)
    legend: dict[str, str] = Field(default_factory=dict)


class NoulA(BaseModel):
    type: Literal["noul"]
    noul: float


Answer = Annotated[ChoiceA | ScoreA | NoulA, Field(discriminator="type")]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class DecideResult(BaseModel):
    answers: dict[str, Answer] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)
    model: str = ""


DecideFn = Callable[[str, dict[str, Question]], DecideResult]
