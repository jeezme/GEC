import base64
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import db
from config import MAIN_URL, TEAMS

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


def _parse_amount(text: str) -> int:
    cleaned = re.sub(r"[^\d]", "", text)
    return int(cleaned) if cleaned else 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def scrape_global(scraped_at: str) -> dict:
    log.info("Scraping page principale %s", MAIN_URL)
    resp = requests.get(MAIN_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    total_dons = 0
    total_objectif = 0

    total_tag = soup.select_one("span#total_dons")
    if total_tag:
        total_dons = _parse_amount(total_tag.get_text())

    objectif_tag = soup.select_one("span#total_event_dons")
    if objectif_tag:
        total_objectif = _parse_amount(objectif_tag.get_text())

    db.insert_global(total_dons, total_objectif, scraped_at)
    log.info("Global: %d / %d", total_dons, total_objectif)
    return {"total_dons": total_dons, "total_objectif": total_objectif}


def scrape_team(team: dict, scraped_at: str):
    slug = team["slug"]
    dept = team["dept"]
    url = f"{MAIN_URL}/equipe/{slug}"
    log.info("Scraping equipe %s", slug)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Erreur HTTP pour %s : %s", slug, exc)
        return

    soup = BeautifulSoup(resp.text, "lxml")

    # Logo
    logo_tag = soup.select_one("div.details-round-log img")
    logo_url = logo_tag["src"] if logo_tag and logo_tag.get("src") else ""
    if logo_url and logo_url.startswith("/"):
        logo_url = MAIN_URL + logo_url
    # Nom equipe
    name_tag = soup.select_one("h3.logo-text")
    team_name = name_tag.get_text(strip=True) if name_tag else team["name"]

    # Type equipe
    type_tag = soup.select_one("div.details-type p")
    team_type = type_tag.get_text(strip=True) if type_tag else team["type"]

    # Montant collecte
    amount_tag = soup.select_one("h3.dont-text")
    amount = _parse_amount(amount_tag.get_text()) if amount_tag else 0

    # Objectif
    objectif_tags = soup.select("h3.objectif-text")
    objectif = _parse_amount(objectif_tags[-1].get_text()) if objectif_tags else 0

    logo_base64 = db.get_team_logo_base64(slug)
    if logo_url and not logo_base64:
        try:
            r = requests.get(logo_url, headers=HEADERS, timeout=10)
            ext = logo_url.split(".")[-1].split("?")[0].lower()
            mime = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
            logo_base64 = "data:" + mime + ";base64," + base64.b64encode(r.content).decode()
        except Exception:
            pass

    db.insert_team(slug, team_name, logo_url, logo_base64, team_type, dept, amount, objectif, scraped_at)
    log.info("  %s : %d / %d", team_name, amount, objectif)

    time.sleep(1)



def scrape_all():
    scraped_at = _now_iso()
    log.info("Debut scraping global a %s", scraped_at)
    scrape_global(scraped_at)
    time.sleep(1)

    for team in TEAMS:
        scrape_team(team, scraped_at)

    log.info("Scraping termine - %d equipes traitees", len(TEAMS))
