# -*- coding: utf-8 -*-
# © 2026 GigRadar / Bublův hlídač koncertů (Autor: Bubla)

import json
import os
import re
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# ==========================================
# NASTAVENÍ
# ==========================================
NTFY_TOPIC = "bubluv-hlidac-koncertu"
OUTPUT_FILE = "koncerty.json"

# Testovací seznam kapel (2 zkušební CZ/SK + pár světových stálic)
SLEDOVANE_KAPELY = [
    "Škwor",
    "MIG 21",
    "Iron Maiden",
    "Judas Priest",
    "Metallica",
    "Sabaton",
    "Monkey Business",
]

SLEDOVANE_STATY = {"CZ", "SK", "AT", "PL", "DE"}

VYRADIT_SLOVA = [
    "smetanova síň", "rudolfinum", "filharmonie", "symfonický orchestr",
    "vážná hudba", "opera", "balet", "komorní koncert", "country", "dechovka"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
}


def je_nevhodny_zanr(text: str) -> bool:
    lower = (text or "").lower()
    return any(slovo in lower for slovo in VYRADIT_SLOVA)


def parsuj_datum_cz(text: str) -> str:
    m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(202\d)", text or "")
    if m:
        d, mes, r = m.groups()
        return f"{r}-{int(mes):02d}-{int(d):02d}"
    return ""


def nacti_predchozi() -> dict:
    if not os.path.exists(OUTPUT_FILE):
        return {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["id"]: item for item in data.get("concerts", [])}
    except Exception:
        return {}


def zkontroluj_bandsintown() -> list:
    """Zdroj 1: Veřejné API Bandsintown pro sledované kapely (včetně fotek a odkazů)."""
    vysledky = []
    stat_mapa = {
        "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "CZ": "CZ",
        "SLOVAKIA": "SK", "SK": "SK",
        "AUSTRIA": "AT", "AT": "AT",
        "POLAND": "PL", "PL": "PL",
        "GERMANY": "DE", "DE": "DE",
    }

    for kapela in SLEDOVANE_KAPELY:
        try:
            url = f"https://rest.bandsintown.com/artists/{requests.utils.quote(kapela)}/events"
            resp = requests.get(url, params={"app_id": "gigradar_bubla_test"}, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  - Bandsintown [{kapela}]: HTTP {resp.status_code}")
                continue

            events = resp.json()
            if not isinstance(events, list):
                continue

            for ev in events:
                venue = ev.get("venue", {})
                stat_kod = stat_mapa.get((venue.get("country") or "").upper(), "")
                if stat_kod not in SLEDOVANE_STATY:
                    continue

                misto = venue.get("name", "Neznámé místo")
                mesto = venue.get("city", "")
                if je_nevhodny_zanr(f"{kapela} {misto}"):
                    continue

                datum = (ev.get("datetime") or "")[:10]
                offers = ev.get("offers") or []
                ticket_url = offers[0].get("url") if offers else ev.get("url", "")
                poster = ev.get("image_url") or ev.get("thumb_url") or ""

                seller = "Oficiální předprodej"
                for domena, nazev in [
                    ("ticketmaster", "Ticketmaster.cz"),
                    ("ticketportal", "Ticketportal.cz"),
                    ("goout", "GoOut.net"),
                    ("smsticket", "smsticket.cz"),
                    ("ticketstream", "Ticketstream.cz"),
                ]:
                    if domena in ticket_url.lower():
                        seller = nazev
                        break

                vysledky.append({
                    "id": f"bit-{ev.get('id', datum)}",
                    "band": kapela,
                    "venue": misto,
                    "city": mesto,
                    "country": stat_kod,
                    "date": datum,
                    "genre": "Metal" if kapela in ["Iron Maiden", "Judas Priest", "Sabaton", "Metallica"] else "Rock",
                    "seller": seller,
                    "url": ticket_url,
                    "poster": poster,
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"  - Chyba Bandsintown [{kapela}]: {e}")

    print(f"[Zdroj 1 - Bandsintown]: nalezeno {len(vysledky)} akcí.")
    return vysledky


def zkontroluj_o2_arenu() -> list:
    """Zdroj 2: Přímý pokus o čtení programu O2 areny (Praha)."""
    vysledky = []
    url = "https://www.o2arena.cz/akce/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select("article, .event-item, .akce-item, a[href*='/akce/']"):
            text = item.get_text(" ", strip=True)
            datum = parsuj_datum_cz(text)
            if not datum or len(text) < 5 or len(text) > 160 or je_nevhodny_zanr(text):
                continue

            odkaz = item.get("href") or url
            if odkaz.startswith("/"):
                odkaz = "https://www.o2arena.cz" + odkaz

            img = item.find("img")
            poster = ""
            if img:
                poster = img.get("src") or img.get("data-src") or ""
                if poster.startswith("/"):
                    poster = "https://www.o2arena.cz" + poster

            nazev = re.sub(r"\d{1,2}\.\s*\d{1,2}\.\s*202\d", "", text).strip(" -|•")
            if len(nazev) < 3:
                continue

            vysledky.append({
                "id": f"o2-{re.sub(r'[^a-z0-9]', '', nazev.lower())[:25]}-{datum}",
                "band": nazev,
                "venue": "O2 arena",
                "city": "Praha",
                "country": "CZ",
                "date": datum,
                "genre": "Rock",
                "seller": "Ticketmaster.cz",
                "url": odkaz,
                "poster": poster,
            })
    except Exception as e:
        print(f"  - Chyba O2 arena: {e}")

    print(f"[Zdroj 2 - O2 arena]: nalezeno {len(vysledky)} akcí.")
    return vysledky


def odesli_ntfy(nove_akce: list):
    if not nove_akce:
        return
    nadpis = f"GigRadar: {len(nove_akce)} nových koncertů"
    zprava = "\n".join(f"• {a['band']} – {a['city']} ({a['date']})" for a in nove_akce[:5])
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
    print("=== START TESTU SBĚRU DAT ===")
    stare = nacti_predchozi()

    nalezene = []
    nalezene.extend(zkontroluj_bandsintown())
    nalezene.extend(zkontroluj_o2_arenu())

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

    print(f"=== HOTOVO: Celkem {len(serazene)} unikátních akcí, nových: {len(nove_akce)} ===")
    odesli_ntfy(nove_akce)


if __name__ == "__main__":
    main()
