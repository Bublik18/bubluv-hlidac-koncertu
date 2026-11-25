# -*- coding: utf-8 -*-
# © 2026 GigRadar / Bublův hlídač koncertů (Autor: Bubla)

import json
import os
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

NTFY_TOPIC = "bubluv-hlidac-koncertu"
OUTPUT_FILE = "koncerty.json"

SLEDOVANE_KAPELY = [
    "Monkey Business",
    "Judas Priest",
    "Kabát",
    "Iron Maiden",
    "Sabaton",
    "Kryštof",
]

SLEDOVANE_STATY = {"CZ", "SK", "DE", "PL", "AT"}

VYRADIT_KLICOVA_SLOVA = [
    "smetanova síň",
    "rudolfinum",
    "filharmonie",
    "symfonický orchestr",
    "vážná hudba",
    "opera",
    "balet",
    "komorní koncert",
    "varhanní koncert",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GigRadarBubla/1.0)"
}


def je_vazna_hudba(text: str) -> bool:
    lower = (text or "").lower()
    return any(slovo in lower for slovo in VYRADIT_KLICOVA_SLOVA)


def nacti_predchozi_koncerty() -> dict:
    if not os.path.exists(OUTPUT_FILE):
        return {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["id"]: item for item in data.get("concerts", [])}
    except Exception:
        return {}


def zkontroluj_sono_centrum() -> list:
    vysledky = []
    url = "https://www.sonocentrum.cz/program/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select("article, .program-item, .event-item, a[href*='/program/']"):
            nazev = item.get_text(" ", strip=True)
            if not nazev or len(nazev) < 4 or len(nazev) > 140:
                continue
            if je_vazna_hudba(nazev):
                continue

            odkaz = item.get("href") or url
            if odkaz.startswith("/"):
                odkaz = "https://www.sonocentrum.cz" + odkaz

            img_el = item.find("img")
            poster_url = ""
            if img_el:
                poster_url = img_el.get("src") or img_el.get("data-src") or ""
                if poster_url.startswith("/"):
                    poster_url = "https://www.sonocentrum.cz" + poster_url

            datum_match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(202\d)", nazev)
            datum_iso = ""
            if datum_match:
                d, m, y = datum_match.groups()
                datum_iso = f"{y}-{int(m):02d}-{int(d):02d}"

            cisty_nazev = re.sub(r"\d{1,2}\.\s*\d{1,2}\.\s*202\d", "", nazev).strip(" -|•")
            if not cisty_nazev:
                continue

            event_id = f"sono-{re.sub(r'[^a-z0-9]', '', cisty_nazev.lower())[:30]}-{datum_iso}"
            vysledky.append({
                "id": event_id,
                "band": cisty_nazev,
                "venue": "Sono Centrum",
                "city": "Brno",
                "country": "CZ",
                "date": datum_iso or datetime.now().strftime("%Y-%m-%d"),
                "genre": "Pop" if "monkey" in cisty_nazev.lower() else "Rock",
                "seller": "GoOut.net",
                "url": odkaz,
                "poster": poster_url,
            })
    except Exception as e:
        print(f"[Chyba Sono Centrum]: {e}")
    return vysledky


def zkontroluj_turne_kapel() -> list:
    vysledky = []
    app_id = "gigradar_bubla"
    stat_mapa = {
        "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "CZ": "CZ",
        "SLOVAKIA": "SK", "SK": "SK",
        "GERMANY": "DE", "DE": "DE",
        "POLAND": "PL", "PL": "PL",
        "AUSTRIA": "AT", "AT": "AT",
    }

    for kapela in SLEDOVANE_KAPELY:
        try:
            api_url = f"https://rest.bandsintown.com/artists/{requests.utils.quote(kapela)}/events"
            resp = requests.get(api_url, params={"app_id": app_id}, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            events = resp.json()
            if not isinstance(events, list):
                continue

            for ev in events:
                venue_info = ev.get("venue", {})
                stat_kod = stat_mapa.get((venue_info.get("country") or "").upper(), "")
                if stat_kod not in SLEDOVANE_STATY:
                    continue

                misto = venue_info.get("name", "Neznámý sál")
                mesto = venue_info.get("city", "")
                if je_vazna_hudba(f"{kapela} {misto}"):
                    continue

                datum_iso = (ev.get("datetime") or "")[:10]
                offers = ev.get("offers") or []
                ticket_url = offers[0].get("url") if offers else ev.get("url", "")
                poster_url = ev.get("image_url") or ev.get("thumb_url") or ""

                seller = "GoOut.net"
                for domena, nazev_prodejce in [
                    ("ticketmaster", "Ticketmaster.cz"),
                    ("ticketportal", "Ticketportal.cz"),
                    ("goout", "GoOut.net"),
                    ("smsticket", "smsticket.cz"),
                    ("ticketstream", "Ticketstream.cz"),
                ]:
                    if domena in ticket_url.lower():
                        seller = nazev_prodejce
                        break

                zanr = "Pop" if "monkey business" in kapela.lower() else "Metal"
                vysledky.append({
                    "id": f"tour-{ev.get('id', datum_iso)}",
                    "band": kapela,
                    "venue": misto,
                    "city": mesto,
                    "country": stat_kod,
                    "date": datum_iso,
                    "genre": zanr,
                    "seller": seller,
                    "url": ticket_url,
                    "poster": poster_url,
                })
            time.sleep(0.4)
        except Exception as e:
            print(f"[Chyba turné {kapela}]: {e}")
    return vysledky


def odesli_ntfy(nove_akce: list):
    if not nove_akce:
        return
    nadpis = f"GigRadar: {len(nove_akce)} nových koncertů"
    zprava = "\n".join(
        f"• {a['band']} – {a['city']} ({a['date']})" for a in nove_akce[:6]
    )
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=zprava.encode("utf-8"),
            headers={"Title": nadpis.encode("utf-8"), "Priority": "high"},
            timeout=10,
        )
    except Exception as e:
        print(f"[Chyba ntfy]: {e}")


def main():
    stare = nacti_predchozi_koncerty()
    nalezene = zkontroluj_sono_centrum() + zkontroluj_turne_kapel()

    unikatni = {}
    nove_akce = []
    for akce in nalezene:
        eid = akce["id"]
        if eid in unikatni:
            continue
        je_nove = eid not in stare
        akce["isNew"] = je_nove
        unikatni[eid] = akce
        if je_nove:
            nove_akce.append(akce)

    serazene = sorted(unikatni.values(), key=lambda x: x.get("date", "9999-99-99"))
    vystup = {
        "updatedAt": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "concerts": serazene,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(vystup, f, ensure_ascii=False, indent=2)

    odesli_ntfy(nove_akce)


if __name__ == "__main__":
    main()
