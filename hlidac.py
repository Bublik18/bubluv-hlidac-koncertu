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
    "Nightwish",
    "Harlej",
    "Škwor",
    "Tři sestry",
]

SLEDOVANE_STATY = {"CZ", "SK", "DE", "PL", "AT"}

# Větší sály a kluby nad 500 míst napříč sledovanými státy a městy (CZ, SK, AT, PL, DE)
SLEDOVANE_SALY_NAD_500 = [
    # Česko (Brno, Praha, Ostrava, Olomouc, Plzeň, Zlín)
    {"name": "Sono Centrum", "city": "Brno", "country": "CZ", "capacity": 1200, "url": "https://www.sonocentrum.cz/program/", "seller": "GoOut.net"},
    {"name": "Fléda", "city": "Brno", "country": "CZ", "capacity": 800, "url": "https://www.fleda.cz/program/", "seller": "GoOut.net"},
    {"name": "O2 arena", "city": "Praha", "country": "CZ", "capacity": 18000, "url": "https://www.o2arena.cz/akce/", "seller": "Ticketmaster.cz"},
    {"name": "O2 universum", "city": "Praha", "country": "CZ", "capacity": 4500, "url": "https://www.o2universum.cz/akce/", "seller": "Ticketmaster.cz"},
    {"name": "Forum Karlín", "city": "Praha", "country": "CZ", "capacity": 3000, "url": "https://www.forumkarlin.cz/program/", "seller": "Ticketmaster.cz"},
    {"name": "Roxy", "city": "Praha", "country": "CZ", "capacity": 900, "url": "https://www.roxy.cz/events/", "seller": "GoOut.net"},
    {"name": "Lucerna Music Bar", "city": "Praha", "country": "CZ", "capacity": 800, "url": "https://musicbar.cz/cs/program/", "seller": "GoOut.net"},
    {"name": "Ostravar Aréna", "city": "Ostrava", "country": "CZ", "capacity": 10000, "url": "https://www.ostravar-arena.cz/akce/", "seller": "Ticketportal.cz"},
    {"name": "Masters of Rock Café", "city": "Zlín", "country": "CZ", "capacity": 850, "url": "https://www.mastersofrockcafe.cz/program/", "seller": "Ticketportal.cz"},
    # Slovensko (Bratislava, Košice)
    {"name": "Majestic Music Club (MMC)", "city": "Bratislava", "country": "SK", "capacity": 800, "url": "https://www.majestic.sk/program/", "seller": "Ticketportal.sk"},
    {"name": "TIPOS Aréna", "city": "Bratislava", "country": "SK", "capacity": 10000, "url": "https://www.ticketportal.sk/", "seller": "Ticketportal.sk"},
    # Rakousko (Vídeň)
    {"name": "Wiener Stadthalle", "city": "Vídeň", "country": "AT", "capacity": 16000, "url": "https://www.stadthalle.com/de/events", "seller": "oeticket.com"},
    {"name": "Gasometer", "city": "Vídeň", "country": "AT", "capacity": 4200, "url": "https://www.planet.tt/", "seller": "oeticket.com"},
    {"name": "Arena Wien", "city": "Vídeň", "country": "AT", "capacity": 1000, "url": "https://arena.wien/Home/Programm", "seller": "oeticket.com"},
    {"name": "Simm City", "city": "Vídeň", "country": "AT", "capacity": 700, "url": "https://www.planet.tt/", "seller": "oeticket.com"},
    # Polsko (Krakov, Varšava, Katovice)
    {"name": "TAURON Arena Kraków", "city": "Krakov", "country": "PL", "capacity": 15000, "url": "https://www.tauronarenakrakow.pl/wydarzenia/", "seller": "Ticketmaster.pl"},
    {"name": "Klub Studio", "city": "Krakov", "country": "PL", "capacity": 1200, "url": "https://www.klubstudio.pl/koncerty", "seller": "Ticketmaster.pl"},
    {"name": "Klub Kwadrat", "city": "Krakov", "country": "PL", "capacity": 700, "url": "https://klubkwadrat.pl/", "seller": "Ticketmaster.pl"},
    {"name": "Progresja", "city": "Varšava", "country": "PL", "capacity": 2000, "url": "https://progresja.com/events/", "seller": "Ticketmaster.pl"},
    # Německo (Mnichov, Stuttgart, Berlín, Drážďany)
    {"name": "Olympiahalle", "city": "Mnichov", "country": "DE", "capacity": 15500, "url": "https://www.olympiapark.de/de/veranstaltungen", "seller": "Eventim.de"},
    {"name": "Zenith", "city": "Mnichov", "country": "DE", "capacity": 5800, "url": "https://www.zenith-muenchen.de/programm/", "seller": "Eventim.de"},
    {"name": "Backstage Werk", "city": "Mnichov", "country": "DE", "capacity": 1200, "url": "https://backstage.eu/veranstaltungen/live.html", "seller": "Eventim.de"},
    {"name": "Hanns-Martin-Schleyer-Halle", "city": "Stuttgart", "country": "DE", "capacity": 15500, "url": "https://www.schleyerhalle.de/veranstaltungen/", "seller": "Eventim.de"},
    {"name": "LKA Longhorn", "city": "Stuttgart", "country": "DE", "capacity": 1500, "url": "https://www.lka-longhorn.de/", "seller": "Eventim.de"},
    {"name": "Im Wizemann", "city": "Stuttgart", "country": "DE", "capacity": 1300, "url": "https://imwizemann.de/programm/", "seller": "Eventim.de"},
]

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
    "country",
    "dechovka",
    "kabinet múz",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}


def je_nevhodna_akce(text: str) -> bool:
    lower = (text or "").lower()
    return any(slovo in lower for slovo in VYRADIT_KLICOVA_SLOVA)


def parsuj_datum(text: str) -> str:
    m_cz = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(202\d)", text or "")
    if m_cz:
        d, mes, r = m_cz.groups()
        return f"{r}-{int(mes):02d}-{int(d):02d}"
    m_iso = re.search(r"(202\d)-(\d{2})-(\d{2})", text or "")
    if m_iso:
        return m_iso.group(0)
    return ""


def odhadni_zanr(text: str) -> str:
    lower = (text or "").lower()
    if any(k in lower for k in ["monkey business", "pop", "funk", "disco", "soul"]):
        return "Pop"
    if any(k in lower for k in ["rap", "hip hop", "hip-hop", "yzomandias", "viktor sheen", "kontrafakt"]):
        return "Rap"
    if any(k in lower for k in ["metal", "judas priest", "iron maiden", "sabaton", "nightwish", "metallica", "slipknot", "slayer"]):
        return "Metal"
    return "Rock"


def nacti_predchozi_koncerty() -> dict:
    if not os.path.exists(OUTPUT_FILE):
        return {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["id"]: item for item in data.get("concerts", [])}
    except Exception:
        return {}


def zkontroluj_saly_nad_500() -> list:
    vysledky = []
    for sal in SLEDOVANE_SALY_NAD_500:
        if sal.get("capacity", 0) < 500:
            continue
        url = sal["url"]
        try:
            resp = requests.get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            base_domain = "/".join(url.split("/")[:3])

            nalezeno_v_salu = 0
            for item in soup.select("article, .event-item, .program-item, .akce-item, .event, .concert, li.event, a[href*='program'], a[href*='event'], a[href*='akce'], a[href*='koncert']"):
                text = item.get_text(" ", strip=True)
                if not text or len(text) < 5 or len(text) > 160 or je_nevhodna_akce(text):
                    continue

                datum_iso = parsuj_datum(text)
                if not datum_iso:
                    continue

                cisty_nazev = re.sub(r"\d{1,2}\.\s*\d{1,2}\.\s*202\d", "", text)
                cisty_nazev = re.sub(r"202\d-\d{2}-\d{2}", "", cisty_nazev).strip(" -|•:/")
                if not cisty_nazev or len(cisty_nazev) < 3:
                    continue

                odkaz = item.get("href") or ""
                if not odkaz:
                    a_tag = item.find("a", href=True)
                    odkaz = a_tag["href"] if a_tag else url
                if odkaz.startswith("/"):
                    odkaz = base_domain + odkaz
                elif not odkaz.startswith("http"):
                    odkaz = url

                img_el = item.find("img")
                poster_url = ""
                if img_el:
                    poster_url = img_el.get("src") or img_el.get("data-src") or ""
                    if poster_url.startswith("/"):
                        poster_url = base_domain + poster_url

                slug_sal = re.sub(r"[^a-z0-9]", "", sal["name"].lower())[:12]
                slug_akce = re.sub(r"[^a-z0-9]", "", cisty_nazev.lower())[:26]
                event_id = f"venue-{slug_sal}-{slug_akce}-{datum_iso}"

                vysledky.append({
                    "id": event_id,
                    "band": cisty_nazev,
                    "venue": sal["name"],
                    "city": sal["city"],
                    "country": sal["country"],
                    "date": datum_iso,
                    "genre": odhadni_zanr(cisty_nazev),
                    "seller": sal["seller"],
                    "url": odkaz,
                    "poster": poster_url,
                })
                nalezeno_v_salu += 1
                if nalezeno_v_salu >= 25:
                    break
            time.sleep(0.25)
        except Exception as e:
            print(f"[Chyba sálu {sal['name']}]: {e}")
    return vysledky


def zkontroluj_live_nation() -> list:
    vysledky = []
    zdroje = [
        ("https://www.livenation.cz/event/allevents", "CZ", "Praha", "Ticketmaster.cz"),
        ("https://www.livenation.sk/event/allevents", "SK", "Bratislava", "Ticketportal.sk"),
        ("https://www.livenation.at/event/allevents", "AT", "Vídeň", "oeticket.com"),
        ("https://www.livenation.de/event/allevents", "DE", "Mnichov", "Eventim.de"),
        ("https://www.livenation.pl/event/allevents", "PL", "Krakov", "Ticketmaster.pl"),
    ]
    for url, stat_kod, vychozi_mesto, prodejce in zdroje:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            for item in soup.select("li.result-card, .event-card, a[href*='/show/']"):
                text = item.get_text(" ", strip=True)
                if not text or len(text) < 5 or len(text) > 180 or je_nevhodna_akce(text):
                    continue

                odkaz = item.get("href") or url
                if odkaz.startswith("/"):
                    base = url.split("/event/")[0]
                    odkaz = base + odkaz

                img_el = item.find("img")
                poster_url = ""
                if img_el:
                    poster_url = img_el.get("src") or img_el.get("data-src") or ""

                datum_iso = parsuj_datum(text) or datetime.now().strftime("%Y-%m-%d")
                cisty_nazev = re.sub(r"\d{1,2}\.\s*\d{1,2}\.\s*202\d", "", text).strip(" -|•")[:90]
                if not cisty_nazev:
                    continue

                event_id = f"ln-{stat_kod.lower()}-{re.sub(r'[^a-z0-9]', '', cisty_nazev.lower())[:28]}-{datum_iso}"
                vysledky.append({
                    "id": event_id,
                    "band": cisty_nazev,
                    "venue": "Live Nation",
                    "city": vychozi_mesto,
                    "country": stat_kod,
                    "date": datum_iso,
                    "genre": odhadni_zanr(cisty_nazev),
                    "seller": prodejce,
                    "url": odkaz,
                    "poster": poster_url,
                })
        except Exception as e:
            print(f"[Chyba Live Nation {stat_kod}]: {e}")
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
                if je_nevhodna_akce(f"{kapela} {misto}"):
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
                    ("eventim", "Eventim.de"),
                    ("oeticket", "oeticket.com"),
                ]:
                    if domena in ticket_url.lower():
                        seller = nazev_prodejce
                        break

                vysledky.append({
                    "id": f"tour-{ev.get('id', datum_iso)}",
                    "band": kapela,
                    "venue": misto,
                    "city": mesto,
                    "country": stat_kod,
                    "date": datum_iso,
                    "genre": odhadni_zanr(kapela),
                    "seller": seller,
                    "url": ticket_url,
                    "poster": poster_url,
                })
            time.sleep(0.35)
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
    nalezene = (
        zkontroluj_saly_nad_500()
        + zkontroluj_live_nation()
        + zkontroluj_turne_kapel()
    )

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
