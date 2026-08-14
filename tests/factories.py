from __future__ import annotations

import json
from pathlib import Path


def ball(
    *,
    batting: str,
    runs: int = 0,
    legal: bool = True,
    wicket: bool = False,
    four: bool = False,
    six: bool = False,
    name: str | None = None,
    over: float = 0.1,
    batsman: str = "Batter One",
    bowler: str = "Bowler One",
) -> dict:
    if name is None:
        if wicket:
            name = "Clean Bowled"
        elif six:
            name = "SIX"
        elif four:
            name = "FOUR"
        elif runs == 0:
            name = "No Run"
        else:
            name = f"{runs} Run" if runs == 1 else f"{runs} Runs"
    return {
        "ball": over,
        "updated_at": "2024-05-01 07:01:00 PM IST",
        "id": 1,
        "name": batting,
        "score": {
            "name": name,
            "runs": runs,
            "four": four,
            "six": six,
            "bye": 0,
            "leg_bye": 0,
            "is_wicket": wicket,
            "ball": legal,
            "out": wicket,
        },
        "batsman": {"id": 1, "fullname": batsman},
        "bowler": {"id": 2, "fullname": bowler},
    }


def comment(text: str, upvotes: int = 1) -> dict:
    return {"timestamp": "2024-05-01 07:01:00 PM", "comment": text, "upvotes": upvotes}


def odds_entry(last_update: str, team_a: str, price_a: float, team_b: str, price_b: float) -> dict:
    return {
        "last_update": last_update,
        "odds": [{"name": team_a, "price": price_a}, {"name": team_b, "price": price_b}],
    }


def chunk(
    name: str,
    *,
    start: str,
    end: str,
    comments: list[dict],
    odds: list[dict],
    balls: list[dict] | None = None,
    pregame: bool = False,
    innings_break: bool = False,
) -> dict:
    body = {
        "name": name,
        "start_time": start,
        "end_time": end,
        "is_pregame": pregame,
        "is_innings_break": innings_break,
        "comments": comments,
        "odds": odds,
    }
    if balls is not None:
        body["balls"] = balls
    return body


def write_match(
    root: Path,
    match_id: int,
    *,
    team_a: str,
    team_b: str,
    chunks: list[dict],
    winner_id: int,
    local_id: int,
    visitor_id: int,
) -> None:
    (root / "chunks").mkdir(parents=True, exist_ok=True)
    (root / "balls").mkdir(parents=True, exist_ok=True)
    (root / "odds").mkdir(parents=True, exist_ok=True)
    match = {
        "match_info": {
            "team1": {"name": team_a, "xi": []},
            "team2": {"name": team_b, "xi": []},
        },
        "chunks": chunks,
    }
    (root / "chunks" / f"{match_id}.json").write_text(json.dumps(match), encoding="utf-8")
    all_balls = []
    for ch in chunks:
        all_balls.extend(ch.get("balls") or [])
    balls_doc = {
        "summary": {
            "id": match_id,
            "round": "Test",
            "localteam_id": local_id,
            "visitorteam_id": visitor_id,
            "starting_at": "2024-05-01 07:00:00 PM IST",
            "note": f"synthetic winner id {winner_id}",
            "venue_id": 58,
            "winner_team_id": winner_id,
        },
        "balls": all_balls,
    }
    (root / "balls" / f"{match_id}.json").write_text(json.dumps(balls_doc), encoding="utf-8")
    odds = []
    for ch in chunks:
        odds.extend(ch.get("odds") or [])
    (root / "odds" / f"{match_id}.json").write_text(json.dumps(odds), encoding="utf-8")
