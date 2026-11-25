import json
import os
from datetime import datetime, timezone
import requests

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "gigradar-bubla")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

EXCLUDED_KEYWORDS = {
    "classical", "vážná", "filharmonie", "opera", "symphony",
    "country", "folk", "lidovky", "blasmusik", "volksmusik"
}

VENUES_500_PLUS = {
    "Brno": [
        {"venue": "Sono Centrum", "capacity": 1200, "country": "CZ"},
        {"venue": "Arena Brno", "capacity": 13300, "country": "CZ"},
    ],
    "Praha": [
        {"venue": "Palác Akropolis", "capacity": 700, "country": "CZ"},
        {"venue": "Lucerna Music Bar", "capacity": 850, "country": "CZ"},
        {"venue": "Velký sál Lucerny", "capacity": 2500, "country": "CZ"},
        {"venue": "Forum Karlín", "capacity": 3000, "country": "CZ"},
        {"venue": "O2 arena", "capacity": 18000, "country": "CZ"},
    ],
    "Stuttgart": [
        {"venue": "LKA Longhorn", "capacity": 1500, "country": "DE"},
        {"venue": "Im Wizemann", "capacity": 1000, "country": "DE"},
        {"venue": "Porsche-Arena", "capacity": 6200, "country": "DE"},
        {"venue": "Hanns-Martin-Schleyer-Halle", "capacity": 15500, "country": "DE"},
    ],
    "Berlin": [
        {"venue": "SO36", "capacity": 500, "country": "DE"},
        {"venue": "Columbiahalle", "capacity": 3500, "country": "DE"},
        {"venue": "Uber Arena", "capacity": 17000, "country": "DE"},
    ],
    "Bratislava": [
        {"venue": "Majestic Music Club (MMC)", "capacity": 1000, "country": "SK"},
        {"venue": "Tipos Aréna", "capacity": 10000, "country": "SK"},
    ],
    "Varšava": [
        {"venue": "Progresja", "capacity": 1800, "country": "PL"},
        {"venue": "COS Torwar", "capacity": 6500, "country": "PL"},
    ],
}

DEFAULT_WATCHLIST = [
    "Monkey Business",
    "The Dead Daisies",
    "Judas Priest",
    "Iron Maiden",
    "Sabaton",
    "Kabát",
]


def is_excluded(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in EXCLUDED_KEYWORDS)


def send_ntfy(message: str, title: str = "GigRadar") -> None:
    try:
        requests.post(
            f"{NTFY_SERVER.rstrip('/')}/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Tags": "guitar,ticket"},
            timeout=15,
        )
    except Exception:
        pass


def build_concerts() -> list[dict]:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sample_events = [
        {
            "id": "gr-sono-mb",
            "band": "Monkey Business",
            "venue": "Sono Centrum",
            "city": "Brno",
            "country": "CZ",
            "capacity": 1200,
            "date": "2026-12-11",
            "genre": "Pop",
            "seller": "GoOut",
            "url": "https://goout.net",
            "poster": "",
            "isNew": True,
        },
        {
            "id": "gr-akropolis-dd",
            "band": "The Dead Daisies",
            "venue": "Palác Akropolis",
            "city": "Praha",
            "country": "CZ",
            "capacity": 700,
            "date": "2027-03-19",
            "genre": "Rock",
            "seller": "Ticketmaster",
            "url": "https://www.ticketmaster.cz",
            "poster": "",
            "isNew": True,
        },
        {
            "id": "gr-lka-jp",
            "band": "Judas Priest",
            "venue": "LKA Longhorn",
            "city": "Stuttgart",
            "country": "DE",
            "capacity": 1500,
            "date": "2027-02-18",
            "genre": "Metal",
            "seller": "Eventim",
            "url": "https://www.eventim.de",
            "poster": "",
            "isNew": False,
        },
    ]

    valid = []
    for ev in sample_events:
        combined = f"{ev['band']} {ev['venue']} {ev['genre']}"
        if is_excluded(combined):
            continue
        if int(ev.get("capacity", 0)) < 500:
            continue
        if ev.get("date", now_iso) >= now_iso:
            valid.append(ev)
    return valid


def main() -> None:
    events = build_concerts()
    payload = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "schedule": ["09:00", "13:00", "17:00"],
        "minCapacity": 500,
        "venues": VENUES_500_PLUS,
        "watchlist": DEFAULT_WATCHLIST,
        "concerts": events,
    }
    with open("koncerty.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    new_events = [e for e in events if e.get("isNew")]
    if new_events:
        summary = ", ".join(f"{e['band']} ({e['city']})" for e in new_events)
        send_ntfy(f"Nové koncerty: {summary}")


if __name__ == "__main__":
    main()
