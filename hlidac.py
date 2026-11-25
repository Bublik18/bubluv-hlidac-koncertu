# -*- coding: utf-8 -*-
# © 2026 GigRadar (Autor: Bubla)
# Nekomerční rozcestník pro fanoušky

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
    "Nightwish",
    "Harlej",
    "Škwor",
    "Tři sestry",
]

SLEDOVANE_STATY = {"CZ", "SK", "AT", "PL", "DE", "HU"}

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
    "mozart",
    "beethoven",
    "dvořák",
    "janáček",
    "country",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GigRadar/1.0)"
}


def je_vyrazeny_zanr(text: str) -> bool:
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
            if je_vyrazeny_zanr(nazev):
                continue

            odkaz = item.get("href") or url
            if odkaz.startswith("/"):
                odkaz = "https://www.sonocentrum.cz" + odkaz

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
                "title": "Koncert v Sono Centru",
                "venue": "Sono Centrum",
                "city": "Brno",
                "country": "CZ",
                "date": datum_iso or datetime.now().strftime("%Y-%m-%d"),
                "genre": "Pop" if "monkey" in cisty_nazev.lower() else "Rock",
                "seller": "Sono / Ticketportal",
                "url": odkaz,
            })
    except Exception as e:
        print(f"[Chyba Sono Centrum]: {e}")
    return vysledky


def zkontroluj_turne_kapel() -> list:
    vysledky = []
    app_id = "gigradar_koncerty"
    stat_mapa = {
        "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "CZ": "CZ",
        "SLOVAKIA": "SK", "SK": "SK",
        "AUSTRIA": "AT", "AT": "AT",
        "POLAND": "PL", "PL": "PL",
        "GERMANY": "DE", "DE": "DE",
        "HUNGARY": "HU", "HU": "HU",
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
                if je_vyrazeny_zanr(f"{kapela} {misto}"):
                    continue

                datum_iso = (ev.get("datetime") or "")[:10]
                offers = ev.get("offers") or []
                ticket_url = offers[0].get("url") if offers else ev.get("url", "")

                seller = "Oficiální předprodej"
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

                zanr = "Pop" if "monkey business" in kapela.lower() else ("Metal" if kapela in ["Judas Priest", "Iron Maiden", "Sabaton", "Nightwish"] else "Rock")
                vysledky.append({
                    "id": f"tour-{ev.get('id', datum_iso)}",
                    "band": kapela,
                    "title": ev.get("title") or f"{kapela} – Live",
                    "venue": misto,
                    "city": mesto,
                    "country": stat_kod,
                    "date": datum_iso,
                    "genre": zanr,
                    "seller": seller,
                    "url": ticket_url,
                })
            time.sleep(0.4)
        except Exception as e:
            print(f"[Chyba turné {kapela}]: {e}")
    return vysledky


def odesli_ntfy(nove_akce: list):
    if not nove_akce:
        return

    nadpis = f"GigRadar: {len(nove_akce)} nových koncertů!"
    radky = [
        f"• {a['band']} – {a['venue']} ({a['city']}, {a['country']}) [{a['date']}]"
        for a in nove_akce[:6]
    ]
    if len(nove_akce) > 6:
        radky.append(f"... a dalších {len(nove_akce) - 6} akcí v aplikaci.")

    zprava = "\n".join(radky)
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=zprava.encode("utf-8"),
            headers={
                "Title": nadpis.encode("utf-8"),
                "Priority": "high",
                "Tags": "guitar,loudspeaker",
            },
            timeout=10,
        )
        print("Push notifikace přes ntfy úspěšně odeslána.")
    except Exception as e:
        print(f"[Chyba ntfy]: {e}")


def main():
    print("Spouštím GigRadar...")
    stare = nacti_predchozi_koncerty()

    nalezene = []
    nalezene.extend(zkontroluj_sono_centrum())
    nalezene.extend(zkontroluj_turne_kapel())

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
        "newCount": len(nove_akce),
        "concerts": serazene,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(vystup, f, ensure_ascii=False, indent=2)

    print(f"Hotovo! Celkem {len(serazene)} koncertů, z toho {len(nove_akce)} nových.")
    odesli_ntfy(nove_akce)


if __name__ == "__main__":
    main()
