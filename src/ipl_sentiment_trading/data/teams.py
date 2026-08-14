"""Canonical IPL 2024 team names, abbreviations, and Sportmonks IDs."""

from __future__ import annotations

from ipl_sentiment_trading.domain.models import TeamRef

# Odds dumps use "Royal Challengers Bangalore"; chunks use "Bengaluru".
_CANONICAL: dict[str, str] = {
    "chennai super kings": "Chennai Super Kings",
    "csk": "Chennai Super Kings",
    "delhi capitals": "Delhi Capitals",
    "dc": "Delhi Capitals",
    "delhi daredevils": "Delhi Capitals",
    "punjab kings": "Punjab Kings",
    "pbks": "Punjab Kings",
    "kxip": "Punjab Kings",
    "kings xi punjab": "Punjab Kings",
    "kolkata knight riders": "Kolkata Knight Riders",
    "kkr": "Kolkata Knight Riders",
    "knight riders": "Kolkata Knight Riders",
    "mumbai indians": "Mumbai Indians",
    "mi": "Mumbai Indians",
    "rajasthan royals": "Rajasthan Royals",
    "rr": "Rajasthan Royals",
    "royals": "Rajasthan Royals",
    "royal challengers bengaluru": "Royal Challengers Bengaluru",
    "royal challengers bangalore": "Royal Challengers Bengaluru",
    "royal challengers": "Royal Challengers Bengaluru",
    "rcb": "Royal Challengers Bengaluru",
    "sunrisers hyderabad": "Sunrisers Hyderabad",
    "srh": "Sunrisers Hyderabad",
    "sunrisers": "Sunrisers Hyderabad",
    "gujarat titans": "Gujarat Titans",
    "gt": "Gujarat Titans",
    "lucknow super giants": "Lucknow Super Giants",
    "lsg": "Lucknow Super Giants",
    "super giants": "Lucknow Super Giants",
}

ABBREVIATION: dict[str, str] = {
    "Chennai Super Kings": "CSK",
    "Delhi Capitals": "DC",
    "Punjab Kings": "PBKS",
    "Kolkata Knight Riders": "KKR",
    "Mumbai Indians": "MI",
    "Rajasthan Royals": "RR",
    "Royal Challengers Bengaluru": "RCB",
    "Sunrisers Hyderabad": "SRH",
    "Gujarat Titans": "GT",
    "Lucknow Super Giants": "LSG",
}

SPORTMONKS_ID: dict[str, int] = {
    "Chennai Super Kings": 2,
    "Delhi Capitals": 3,
    "Punjab Kings": 4,
    "Kolkata Knight Riders": 5,
    "Mumbai Indians": 6,
    "Rajasthan Royals": 7,
    "Royal Challengers Bengaluru": 8,
    "Sunrisers Hyderabad": 9,
    "Gujarat Titans": 1976,
    "Lucknow Super Giants": 1979,
}

ID_TO_CANONICAL: dict[int, str] = {v: k for k, v in SPORTMONKS_ID.items()}

# Fan / media nicknames used for comment attribution (not for odds matching).
TEAM_NICKNAMES: dict[str, tuple[str, ...]] = {
    "Chennai Super Kings": (
        "chennai super kings",
        "csk",
        "thala",
        "yellow army",
        "whistle podu",
        "dhoni",
        "msd",
        "jadeja",
        "ruturaj",
    ),
    "Delhi Capitals": (
        "delhi capitals",
        "delhi daredevils",
        "pant",
        "jfm",
        "fraser-mcgurk",
        "stubbs",
        "axar",
    ),
    "Punjab Kings": (
        "punjab kings",
        "pbks",
        "kxip",
        "kings xi",
        "shashank",
        "livingstone",
        "arshdeep",
    ),
    "Kolkata Knight Riders": (
        "kolkata knight riders",
        "kkr",
        "knight riders",
        "knights",
        "korbo lorbo jeetbo",
        "starc",
        "narine",
        "russell",
        "rinku",
        "shreyas iyer",
        "salt",
    ),
    "Mumbai Indians": (
        "mumbai indians",
        "hitman",
        "rohit",
        "bumrah",
        "sky",
        "surya",
        "hardik",
        "tilak",
        "naman dhir",
    ),
    "Rajasthan Royals": (
        "rajasthan royals",
        "halla bol",
        "sanju",
        "samson",
        "buttler",
        "jaiswal",
        "chahal",
        "boult",
        "parag",
    ),
    "Royal Challengers Bengaluru": (
        "royal challengers bengaluru",
        "royal challengers bangalore",
        "royal challengers",
        "rcb",
        "rcbian",
        "ee sala",
        "playoffs namde",
        "kohli",
        "king kohli",
        "faf",
        "green",
        "maxwell",
        "dk",
        "dinesh karthik",
        "patidar",
    ),
    "Sunrisers Hyderabad": (
        "sunrisers hyderabad",
        "srh",
        "orange army",
        "cummins",
        "head",
        "abhishek",
        "klaasen",
        "natarajan",
        "philips",
        "nkr",
    ),
    "Gujarat Titans": (
        "gujarat titans",
        "sai sudharsan",
        "rashid",
        "shami",
        "gill",
        "saha",
        "tsurge",
        "tushar deshpande",
    ),
    "Lucknow Super Giants": (
        "lucknow super giants",
        "lsg",
        "super giants",
        "kl rahul",
        "pooran",
        "krunal",
        "mayank yadav",
        "stoinis",
        "nortje",
    ),
}

# Short tokens that must be matched as whole words.
SHORT_ALIASES: dict[str, str] = {
    "csk": "Chennai Super Kings",
    "dc": "Delhi Capitals",
    "pbks": "Punjab Kings",
    "kxip": "Punjab Kings",
    "kkr": "Kolkata Knight Riders",
    "mi": "Mumbai Indians",
    "rr": "Rajasthan Royals",
    "rcb": "Royal Challengers Bengaluru",
    "srh": "Sunrisers Hyderabad",
    "gt": "Gujarat Titans",
    "lsg": "Lucknow Super Giants",
    "thala": "Chennai Super Kings",
    "msd": "Chennai Super Kings",
    "hitman": "Mumbai Indians",
}


def canonicalize_team(name: str | None) -> str | None:
    if not name:
        return None
    key = " ".join(name.strip().lower().split())
    if key in _CANONICAL:
        return _CANONICAL[key]
    stripped = name.strip()
    if stripped in ABBREVIATION:
        return stripped
    return stripped


def abbreviation(name: str) -> str:
    canon = canonicalize_team(name) or name
    return ABBREVIATION.get(canon, canon[:3].upper())


def team_ref(name: str, sportmonks_id: int | None = None) -> TeamRef:
    canon = canonicalize_team(name) or name
    sid = sportmonks_id if sportmonks_id is not None else SPORTMONKS_ID.get(canon)
    return TeamRef(name=canon, abbreviation=abbreviation(canon), sportmonks_id=sid)


def winner_from_id(winner_team_id: int | None, fallback_names: tuple[str, str]) -> str | None:
    if winner_team_id is None:
        return None
    mapped = ID_TO_CANONICAL.get(int(winner_team_id))
    if mapped:
        return mapped
    for name in fallback_names:
        canon = canonicalize_team(name)
        if canon and SPORTMONKS_ID.get(canon) == int(winner_team_id):
            return canon
    return None
