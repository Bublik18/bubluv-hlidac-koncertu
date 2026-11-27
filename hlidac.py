# -*- coding: utf-8 -*-
# © 2026 GigRadar / Bublův hlídač koncertů (Autor: Bubla)

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# ==========================================
# NASTAVENÍ
# ==========================================
NTFY_TOPIC = "bubluv-hlidac-koncertu"
OUTPUT_FILE = "koncerty.json"

# České hudební magazíny a koncertní novinky (RSS / články)
CZ_HUDOBNI_WEBY = [
    {
        "name": "Spark Rock Magazine",
        "rss": "https://www.spark-rockmagazine.cz/rss",
        "web": "https://www.spark-rockmagazine.cz/novinky",
        "genre": "Metal",
    },
    {
        "name": "Headliner",
        "rss": "https://www.headliner.cz/rss",
        "web": "https://www.headliner.cz/novinky",
        "genre": "Rock",
    },
    {
        "name": "Musicserver.cz",
        "rss": "https://musicserver.cz/rss/",
        "web": "https://musicserver.cz/novinky/",
        "genre": "Pop",
    },
    {
        "name": "iREPORT.cz",
        "rss": "https://www.ireport.cz/feed",
        "web": "https://www.ireport.cz/clanky/novinky",
        "genre": "Rock",
    },
    {
        "name": "Fakker!",
        "rss": "https://fakker.cz/rss",
        "web": "https://fakker.cz/clanky",
        "genre": "Metal",
    },
]

KONCERTNI_KLICOVA_SLOVA = [
    "koncert", "koncerty", "vystoupí", "přijede", "přijedou", "turné", "tour",
    "o2 arena", "o2 universum", "forum karlín", "sono", "fléda", "lucerna",
    "roxy", "eden", "letňany", "ostravar", "praha", "brno", "ostrava",
    "plzeň", "bratislava", "vídeň", "vstupenky", "předprodej", "open air",
]

VYRADIT_SLOVA = [
    "smetanova síň", "rudolfinum", "filharmonie", "symfonický orchestr",
    "vážná hudba", "opera", "balet", "komorní koncert", "country", "dechovka",
    "zemřel", "zemřela", "úmrtí", "recenze alba", "nový klip", "videoklip"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8"
}


def je_nevhodne(text: str) -> bool:
    lower = (text or "").lower()
    return any(s in lower for s in VYRADIT_SLOVA)


def je_koncertni_zprava(text: str) -> bool:
    lower = (text or "").lower()
    if je_nevhodne(lower):
        return False
    return any(k in lower for k in KONCERTNI_KLICOVA_SLOVA)


def parsuj_datum(text: str) -> str:
    m_cz = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(202\d)", text or "")
    if m_cz:
        d, mes, r = m_cz.groups()
        return f"{r}-{int(mes):02d}-{int(d):02d}"
    m_iso = re.search(r"(202\d)-(\d{2})-(\d{2})", text or "")
    if m_iso:
        return m_iso.group(0)
    return datetime.now().strftime("%Y-%m-%d")


def urci_mesto_a_stat(text: str) -> tuple:
    lower = (text or "").lower()
    mesta = [
        ("brno", "Brno", "CZ"),
        ("sono", "Brno", "CZ"),
        ("fléda", "Brno", "CZ"),
        ("ostrava", "Ostrava", "CZ"),
        ("ostravar", "Ostrava", "CZ"),
        ("plzeň", "Plzeň", "CZ"),
        ("plzni", "Plzeň", "CZ"),
        ("olomouc", "Olomouc", "CZ"),
        ("zlín", "Zlín", "CZ"),
        ("vizovice", "Vizovice", "CZ"),
        ("pardubice", "Pardubice", "CZ"),
        ("hradec králové", "Hradec Králové", "CZ"),
        ("jihlava", "Jihlava", "CZ"),
        ("bratislava", "Bratislava", "SK"),
        ("košice", "Košice", "SK"),
        ("vídeň", "Vídeň", "AT"),
        ("vídni", "Vídeň", "AT"),
        ("varšava", "Varšava", "PL"),
        ("krakov", "Krakov", "PL"),
        ("berlín", "Berlín", "DE"),
        ("mnichov", "Mnichov", "DE"),
        ("praha", "Praha", "CZ"),
        ("praze", "Praha", "CZ"),
        ("o2 arena", "Praha", "CZ"),
        ("forum karlín", "Praha", "CZ"),
        ("lucerna", "Praha", "CZ"),
        ("roxy", "Praha", "CZ"),
        ("letňany", "Praha", "CZ"),
    ]
    for klic, mesto, stat in mesta:
        if klic in lower:
            return mesto, stat
    return "Praha", "CZ"


def odhadni_zanr(text: str, vychozi: str = "Rock") -> str:
    lower = (text or "").lower()
    if any(k in lower for k in ["metal", "thrash", "death", "black", "heavy", "core", "iron maiden", "judas priest", "metallica", "sabaton", "slayer", "slipknot", "korn"]):
        return "Metal"
    if any(k in lower for k in ["hip hop", "hip-hop", "rap", "rapper"]):
        return "Hip hop"
    if any(k in lower for k in ["pop", "funk", "monkey business", "ewa farna", "kryštof"]):
        return "Pop"
    return vychozi


def nacti_predchozi() -> dict:
    if not os.path.exists(OUTPUT_FILE):
        return {}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {item["id"]: item for item in data.get("concerts", [])}
    except Exception:
        return {}


def zkontroluj_rss(zdroj: dict) -> list:
    vysledky = []
    resp = requests.get(zdroj["rss"], headers=HEADERS, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    for item in root.findall(".//item")[:40]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc_raw = item.findtext("description") or ""
        desc = BeautifulSoup(desc_raw, "html.parser").get_text(" ", strip=True)
        plny_text = f"{title} {desc}"

        if not title or not je_koncertni_zprava(plny_text):
            continue

        poster = ""
        enc = item.find("enclosure")
        if enc is not None and enc.get("url"):
            poster = enc.get("url")
        if not poster:
            img_tag = BeautifulSoup(desc_raw, "html.parser").find("img")
            if img_tag:
                poster = img_tag.get("src") or ""

        mesto, stat = urci_mesto_a_stat(plny_text)
        datum = parsuj_datum(plny_text)
        slug = re.sub(r"[^a-z0-9]", "", title.lower())[:32]

        vysledky.append({
            "id": f"news-{slug}-{datum}",
            "band": title[:110],
            "venue": zdroj["name"],
            "city": mesto,
            "country": stat,
            "date": datum,
            "genre": odhadni_zanr(plny_text, zdroj["genre"]),
            "seller": zdroj["name"],
            "url": link or zdroj["web"],
            "poster": poster,
        })
    return vysledky


def zkontroluj_web_clanky(zdroj: dict) -> list:
    vysledky = []
    resp = requests.get(zdroj["web"], headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    base = "/".join(zdroj["web"].split("/")[:3])

    for a in soup.select("article a, h2 a, h3 a, .article a, .news-item a"):
        title = a.get_text(" ", strip=True)
        href = a.get("href") or ""
        if len(title) < 12 or not je_koncertni_zprava(title):
            continue
        if href.startswith("/"):
            href = base + href
        elif not href.startswith("http"):
            continue

        mesto, stat = urci_mesto_a_stat(title)
        datum = parsuj_datum(title)
        slug = re.sub(r"[^a-z0-9]", "", title.lower())[:32]

        vysledky.append({
            "id": f"news-{slug}-{datum}",
            "band": title[:110],
            "venue": zdroj["name"],
            "city": mesto,
            "country": stat,
            "date": datum,
            "genre": odhadni_zanr(title, zdroj["genre"]),
            "seller": zdroj["name"],
            "url": href,
            "poster": "",
        })
    return vysledky


def zkontroluj_hudebni_magaziny() -> list:
    vsechny = []
    for zdroj in CZ_HUDOBNI_WEBY:
        nalezeno = []
        try:
            nalezeno = zkontroluj_rss(zdroj)
            print(f"[{zdroj['name']} - RSS]: nalezeno {len(nalezeno)} koncertních zpráv.")
        except Exception as e_rss:
            print(f"[{zdroj['name']} - RSS selhalo]: {e_rss} -> zkouším web...")
            try:
                nalezeno = zkontroluj_web_clanky(zdroj)
                print(f"[{zdroj['name']} - WEB]: nalezeno {len(nalezeno)} koncertních zpráv.")
            except Exception as e_web:
                print(f"[{zdroj['name']} - WEB selhalo]: {e_web}")
        vsechny.extend(nalezeno)
        time.sleep(0.3)
    return vsechny


def odesli_ntfy(nove_akce: list):
    if not nove_akce:
        return
    nadpis = f"GigRadar: {len(nove_akce)} nových koncertů"
    zprava = "\n".join(f"• {a['band']} ({a['city']})" for a in nove_akce[:5])
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
    print("=== START SBĚRU KONCERTNÍCH NOVINEK ===")
    stare = nacti_predchozi()
    nalezene = zkontroluj_hudebni_magaziny()

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

    serazene = sorted(unikatni.values(), key=lambda x: x.get("date", "9999-99-99"), reverse=True)
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
