"""Best-effort Sportmonks venue labels for IPL 2024. Unknown IDs stay as Venue {id}."""

from __future__ import annotations

VENUES: dict[int, str] = {
    46: "Wankhede Stadium, Mumbai",
    51: "Sawai Mansingh Stadium, Jaipur",
    54: "M. Chinnaswamy Stadium, Bengaluru",
    58: "MA Chidambaram Stadium, Chennai",
    59: "Arun Jaitley Stadium, Delhi",
    62: "Rajiv Gandhi International Stadium, Hyderabad",
    63: "Punjab Cricket Association IS Bindra Stadium, Mohali",
    64: "Eden Gardens, Kolkata",
    134: "Bharat Ratna Shri Atal Bihari Vajpayee Ekana Cricket Stadium, Lucknow",
    140: "Himachal Pradesh Cricket Association Stadium, Dharamshala",
    170: "Barsapara Cricket Stadium, Guwahati",
    182: "Narendra Modi Stadium, Ahmedabad",
    959: "Maharaja Yadavindra Singh International Cricket Stadium, Mullanpur",
}


def venue_label(venue_id: int | None) -> str | None:
    if venue_id is None:
        return None
    return VENUES.get(int(venue_id), f"Venue {venue_id}")
