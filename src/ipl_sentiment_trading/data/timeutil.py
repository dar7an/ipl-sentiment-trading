"""Parse frozen corpus clocks as naive IST wall times (labels stripped, not converted)."""

from __future__ import annotations

from datetime import datetime

_FORMATS = (
    "%Y-%m-%d %I:%M:%S %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %I:%M:%S %p IST",
)


def parse_corpus_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = " ".join(str(value).strip().split())
    text = text.replace(" IST", "").replace(" ist", "").strip()
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized corpus datetime: {value!r}")
