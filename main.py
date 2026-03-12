import logging
import os
import threading
from datetime import date, datetime

from flask import Flask, jsonify, request

import db
import gender as _gender
from config import DUEL_TEAM_1, DUEL_TEAM_2, TEAMS as _CONFIG_TEAMS, DUEL_DEPT_1, DUEL_DEPT_2, DUEL_DEPT_1_NAME, DUEL_DEPT_2_NAME

app = Flask(__name__)
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "changeme")

os.makedirs("/data", exist_ok=True)

log = logging.getLogger(__name__)

try:
    db.init_db()
except Exception as _e:
    log.error("init_db() echoue au demarrage : %s", _e)

NBSP = " "
EURO = "€"

_HTML_CACHE = {"html": None}


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", NBSP) + NBSP + EURO


def _pct(a: int, b: int) -> float:
    return round(min(a / b * 100, 100), 1) if b else 0.0


def _medal(rank: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(rank, f"#{rank}")


def _img(src: str, width: str, extra: str = "", b64: str = "") -> str:
    if b64:
        src = b64
    elif not src:
        return ""
    return '<img src="' + src + '" width="' + width + '"' + extra + ' onerror="this.remove()">'


def _team_card_html(team: dict, rank: int, size: str = "md") -> str:
    pct = _pct(team.get("amount", 0), team.get("objectif", 1) or 1)
    logo = team.get("logo_url", "")
    logo_size = {"lg": "100", "md": "64", "sm": "40"}.get(size, "64")
    gold = (
        ' style="background:linear-gradient(135deg,#fffbea 0%,#fff8e1 60%);'
        'border-color:#f1c40f;border-width:2px"'
        if rank == 1 else ""
    )
    return (
        '<div class="team-card rank-' + size + '"' + gold + '>'
        '<div class="team-rank">' + _medal(rank) + '</div>'
        + _img(logo, logo_size)
        + '<div class="team-name">' + team.get("team_name", "") + '</div>'
        '<div class="team-amount">' + _fmt(team.get("amount", 0)) + '</div>'
        '<div class="progress-bar-wrap">'
        '<div class="progress-bar" style="width:' + str(pct) + '%"></div></div>'
        '<div class="progress-label">' + str(pct) + "% de l'objectif ("
        + _fmt(team.get("objectif", 0)) + ')</div></div>'
    )


def _card(cid: str, title: str, body: str, save_filename: str, generated_at: str) -> str:
    return (
        '<div class="card" id="' + cid + '">'
        '<div class="card-header">'
        '<h2>' + title + '</h2>'
        '</div>'
        '<div class="card-body">' + body + '</div>'
        '</div>'
    )


def _skier_row_html(skier: dict, rank: int, show_delta: bool = False, show_team: bool = False) -> str:
    first = skier.get("first_name", "")
    last = skier.get("last_name", "").upper()
    name = (first + " " + last).strip()
    team_name = skier.get("team_name", "")
    amount = skier.get("delta_24h", skier.get("amount", 0)) if show_delta else skier.get("amount", 0)
    big = rank == 1 and show_delta
    sz = "56" if big else "40"
    cls = "skier-row skier-top1" if big else "skier-row"
    team_span = '<br><span class="skier-team">' + team_name + '</span>' if show_team and team_name else ""
    photo_html = _img(skier.get("photo_url", ""), sz, ' class="skier-photo"', b64=skier.get("photo_base64") or "")
    return (
        '<div class="' + cls + '">'
        '<span class="skier-rank">' + _medal(rank) + '</span>'
        + photo_html
        + '<span class="skier-name">' + name + team_span + '</span>'
        + '<span class="skier-amount">' + _fmt(amount) + '</span>'
        '</div>'
    )


def _fmt_don_date(scraped_at: str) -> str:
    try:
        dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        months = ["jan", "fév", "mars", "avr", "mai", "juin",
                  "juil", "août", "sep", "oct", "nov", "déc"]
        return f"{dt.day:02d} {months[dt.month - 1]} à {dt.hour:02d}h{dt.minute:02d}"
    except Exception:
        return scraped_at

def _build_html() -> str:
    today = date.today()
    generated_at = datetime.now().strftime("%d/%m/%Y à %H:%M")

    _config_slugs = {t["slug"] for t in _CONFIG_TEAMS}

    teams = db.get_all_latest_teams()
    teams = [t for t in teams if t.get("team_slug") in _config_slugs]

    teams_delta = db.get_team_24h_delta()

    skiers = db.get_all_latest_skiers()
    skiers = [s for s in skiers if s.get("team_slug") in _config_slugs]
    skiers_delta = db.get_skiers_24h_delta()
    skiers_delta = [s for s in skiers_delta if s.get("team_slug") in _config_slugs]

    recent_dons = db.get_recent_dons(20)
    teams_by_slug = {t["team_slug"]: t for t in teams}

    g = db.get_latest_global()
    total_dons = g["total_dons"]
    total_objectif = g["total_objectif"]

    pct_global = _pct(total_dons, total_objectif)
    global_banner = (
        '<div class="global-banner">'
        '🎿 Cagnotte totale : '
        '<span class="global-amount">' + _fmt(total_dons) + '</span>'
        ' / ' + _fmt(total_objectif)
        + '<div class="progress-bar-wrap global-bar">'
        '<div class="progress-bar" style="width:' + str(pct_global) + '%"></div></div>'
        '<div class="global-label">' + str(pct_global) + "% de l'objectif</div>"
        '</div>'
    )


    _dept_by_slug = {c["slug"]: c["dept"] for c in _CONFIG_TEAMS}
    teams_73 = [t for t in teams if _dept_by_slug.get(t.get("team_slug", "")) == DUEL_DEPT_1]
    teams_74 = [t for t in teams if _dept_by_slug.get(t.get("team_slug", "")) == DUEL_DEPT_2]
    total_73 = sum(t["amount"] for t in teams_73)
    total_74 = sum(t["amount"] for t in teams_74)
    total_depts = total_73 + total_74 or 1
    pct_73 = _pct(total_73, total_depts)
    pct_74 = _pct(total_74, total_depts)
    logos_73 = "".join(
        _img(t.get("logo_url", ""), "32", ' title="' + t.get("team_name", "") + '"')
        for t in teams_73 if t.get("logo_url")
    )
    logos_74 = "".join(
        _img(t.get("logo_url", ""), "32", ' title="' + t.get("team_name", "") + '"')
        for t in teams_74 if t.get("logo_url")
    )
    card3_body = (
        '<div class="versus-wrap">'
        '<div class="versus-side">'
        '<div class="side-title" style="color:#e67e22">' + DUEL_DEPT_1 + ' ' + DUEL_DEPT_1_NAME.upper() + '</div>'
        '<div class="side-total">' + _fmt(total_73) + '</div>'
        '<div class="side-stats">' + str(len(teams_73)) + ' équipes</div>'
        '<div class="logos-mosaic">' + logos_73 + '</div></div>'
        '<div class="versus-center"><div class="vs-label">VS</div>'
        '<div class="dual-bar">'
        '<div style="height:100%;width:' + str(pct_73) + '%;background:#e67e22;display:inline-block;border-radius:4px 0 0 4px"></div>'
        '<div style="height:100%;width:' + str(pct_74) + '%;background:#27ae60;display:inline-block;border-radius:0 4px 4px 0"></div>'
        '</div>'
        '<div class="dual-pcts">'
        '<span style="color:#e67e22">' + str(pct_73) + '%</span> / '
        '<span style="color:#27ae60">' + str(pct_74) + '%</span></div></div>'
        '<div class="versus-side">'
        '<div class="side-title" style="color:#27ae60">' + DUEL_DEPT_2 + ' ' + DUEL_DEPT_2_NAME.upper() + '</div>'
        '<div class="side-total">' + _fmt(total_74) + '</div>'
        '<div class="side-stats">' + str(len(teams_74)) + ' équipes</div>'
        '<div class="logos-mosaic">' + logos_74 + '</div></div></div>'
    )

    team1 = next((t for t in teams if t["team_slug"] == DUEL_TEAM_1), None)
    team2 = next((t for t in teams if t["team_slug"] == DUEL_TEAM_2), None)
    a1 = team1["amount"] if team1 else 0
    a2 = team2["amount"] if team2 else 0
    ecart = abs(a1 - a2)
    leading1 = a1 >= a2
    n1 = team1["team_name"] if team1 else DUEL_TEAM_1
    n2 = team2["team_name"] if team2 else DUEL_TEAM_2

    def _duel_half(team, leading):
        if not team:
            return '<div class="duel-half">Equipe introuvable</div>'
        pct = _pct(team["amount"], team.get("objectif", 1) or 1)
        glow = " duel-leading" if leading else ""
        logo_img = _img(team.get("logo_url", ""), "80")
        return (
            '<div class="duel-half' + glow + '">' + logo_img
            + '<div class="duel-name">' + team.get("team_name", "") + '</div>'
            '<div class="duel-amount">' + _fmt(team.get("amount", 0)) + '</div>'
            '<div class="progress-bar-wrap">'
            '<div class="progress-bar" style="width:' + str(pct) + '%"></div></div>'
            '<div class="progress-label">' + str(pct) + '% objectif</div>'
            '</div>'
        )

    card4_body = (
        '<div class="duel-wrap">'
        + _duel_half(team1, leading1)
        + '<div class="duel-center">'
          '<div class="vs-label">&#x2694;&#xFE0F;</div>'
          '<div class="ecart-label">Ecart</div>'
          '<div class="ecart-amount">' + _fmt(ecart) + '</div></div>'
        + _duel_half(team2, not leading1)
        + '</div>'
    )

    top10_teams = teams_delta[:10]
    rows5 = ""
    for i, d in enumerate(top10_teams, 1):
        t5 = teams_by_slug.get(d["team_slug"], {})
        logo_img = _img(t5.get("logo_url", ""), "32")
        trend = "↑" if d["delta_24h"] > 0 else "→"
        tc = "#48cfad" if d["delta_24h"] > 0 else "#aaa"
        rows5 += (
            '<tr><td>' + _medal(i) + '</td><td>' + logo_img + '</td>'
            '<td>' + t5.get("team_name", d["team_slug"]) + '</td>'
            '<td style="color:#48cfad;font-weight:700">+' + _fmt(d["delta_24h"]) + '</td>'
            '<td>' + _fmt(d["amount"]) + '</td>'
            '<td style="color:' + tc + ';font-size:1.3em">' + trend + '</td></tr>'
        )
    card5_body = (
        '<table class="rank-table">'
        '<thead><tr><th>Rang</th><th></th><th>Equipe</th><th>+24h</th><th>Total</th><th></th></tr></thead>'
        '<tbody>' + rows5 + '</tbody></table>'
    )

    # CARD 6 - Meilleurs skieurs 24h
    top10_sk = skiers_delta[:10]
    for s in top10_sk:
        s["team_name"] = teams_by_slug.get(s.get("team_slug", ""), {}).get("team_name", "")
    rows6 = "".join(
        _skier_row_html(s, i + 1, show_delta=True, show_team=True)
        for i, s in enumerate(top10_sk)
    )
    card6_body = '<div class="skiers-list">' + rows6 + '</div>'

    # CARD 7 - Top 20 skieurs (total)
    top20_sk = skiers[:20]
    for s in top20_sk:
        s["team_name"] = teams_by_slug.get(s.get("team_slug", ""), {}).get("team_name", "")
    rows7 = ""
    for i, s in enumerate(top20_sk):
        row = _skier_row_html(s, i + 1, show_team=True)
        if i == 0:
            row = '<div class="skier-gold">' + row + '</div>'
        rows7 += row
    card7_body = '<div class="skiers-list">' + rows7 + '</div>'

    # CARD 8 - Classement des equipes par montant collecte
    teams_sorted_amount = sorted(
        teams, key=lambda t: t.get("amount", 0), reverse=True
    )
    rows8 = ""
    for i, t in enumerate(teams_sorted_amount, 1):
        pct_t = _pct(t.get("amount", 0), t.get("objectif", 1) or 1)
        bar_col = "#27ae60" if pct_t >= 100 else ("#f39c12" if pct_t >= 50 else "#e74c3c")
        logo_td = _img(t.get("logo_url", ""), "32")
        medal_td = _medal(i) if i <= 3 else '<span style="color:#888;font-size:.9em">' + str(i) + '</span>'
        rows8 += (
            '<tr>'
            '<td style="text-align:center;font-size:1.2em;width:36px">' + medal_td + '</td>'
            '<td>' + logo_td + '</td>'
            '<td style="font-weight:700"><a href="/qr/' + t.get("team_slug", "") + '" target="_blank" style="color:inherit;text-decoration:none">' + t.get("team_name", "") + '</a></td>'
            '<td style="color:#48cfad;font-weight:700">' + _fmt(t.get("amount", 0)) + '</td>'
            '<td style="color:#888">' + _fmt(t.get("objectif", 0)) + '</td>'
            '<td style="width:160px">'
            '<div class="progress-bar-wrap" style="height:10px;margin:0">'
            '<div style="height:100%;width:' + str(min(pct_t, 100)) + '%;background:' + bar_col + ';border-radius:4px"></div>'
            '</div>'
            '<div style="font-size:.8em;color:' + bar_col + ';font-weight:700">' + str(pct_t) + '%</div>'
            '</td>'
            '</tr>'
        )
    total_all = sum(t.get("amount", 0) for t in teams)
    total_obj_all = sum(t.get("objectif", 0) for t in teams)
    pct_all = _pct(total_all, total_obj_all or 1)
    bar_col_all = "#27ae60" if pct_all >= 100 else ("#f39c12" if pct_all >= 50 else "#e74c3c")
    card8_body = (
        '<table class="rank-table">'
        '<thead><tr><th>#</th><th></th><th>Equipe</th><th>Collecté</th><th>Objectif</th><th>Progression</th></tr></thead>'
        '<tbody>' + rows8 + '</tbody></table>'
        '<div class="obj-summary">'
        '<div class="obj-summary-row"><span>Total collecté :</span>'
        '<span style="color:#48cfad;font-weight:900">' + _fmt(total_all) + '</span></div>'
        '<div class="obj-summary-row"><span>Objectif total :</span>'
        '<span style="color:#888">' + _fmt(total_obj_all) + '</span></div>'
        '<div class="progress-bar-wrap" style="height:14px;margin:12px 0 6px">'
        '<div style="height:100%;width:' + str(min(pct_all, 100)) + '%;background:' + bar_col_all + ';border-radius:4px"></div>'
        '</div>'
        '<div style="font-size:1.1em;font-weight:700;color:' + bar_col_all + '">'
        + str(pct_all) + "% de l'objectif global</div>"
        '</div>'
    )

    # CARD 9 - Classement Filles / Garçons
    _overrides = _gender.load_overrides()
    skiers_f = []
    skiers_m = []
    for s in skiers:
        g = _gender.detect_gender(s.get("first_name", ""), _overrides)
        if g == "F":
            skiers_f.append(s)
        else:
            skiers_m.append(s)

    total_f = sum(s.get("amount", 0) for s in skiers_f)
    total_m = sum(s.get("amount", 0) for s in skiers_m)
    total_genders = total_f + total_m or 1
    pct_f = _pct(total_f, total_genders)
    pct_m = _pct(total_m, total_genders)

    top_f = sorted(skiers_f, key=lambda s: s.get("amount", 0), reverse=True)[:5]
    top_m = sorted(skiers_m, key=lambda s: s.get("amount", 0), reverse=True)[:5]
    for s in top_f + top_m:
        s["team_name"] = teams_by_slug.get(s.get("team_slug", ""), {}).get("team_name", "")

    def _gender_top_rows(sk_list):
        return "".join(
            _skier_row_html(s, i + 1, show_team=True)
            for i, s in enumerate(sk_list)
        )

    card9_body = (
        '<div class="versus-wrap">'
        '<div class="versus-side">'
        '<div class="side-title" style="color:#e91e8c">&#9792; FILLES</div>'
        '<div class="side-total" style="color:#e91e8c">' + _fmt(total_f) + '</div>'
        '<div class="side-stats">' + str(len(skiers_f)) + ' skieuses</div>'
        '<div class="duel-top3">' + _gender_top_rows(top_f) + '</div>'
        '</div>'
        '<div class="versus-center">'
        '<div class="dual-bar" style="flex-direction:column;height:auto;gap:8px;background:none">'
        '<div style="height:16px;background:#e0e4ed;border-radius:4px;overflow:hidden;display:flex;width:100%">'
        '<div class="dual-bar-f" style="width:' + str(pct_f) + '%"></div>'
        '<div class="dual-bar-m" style="width:' + str(pct_m) + '%"></div>'
        '</div></div>'
        '<div class="dual-pcts">'
        '<span style="color:#e91e8c">' + str(pct_f) + '%</span>'
        ' / '
        '<span style="color:#3498db">' + str(pct_m) + '%</span>'
        '</div></div>'
        '<div class="versus-side">'
        '<div class="side-title" style="color:#3498db">&#9794; GARÇONS</div>'
        '<div class="side-total" style="color:#3498db">' + _fmt(total_m) + '</div>'
        '<div class="side-stats">' + str(len(skiers_m)) + ' skieurs</div>'
        '<div class="duel-top3">' + _gender_top_rows(top_m) + '</div>'
        '</div>'
        '</div>'
    )

    # CARD 10 - Défi 1000€ (10 mars ~17h → 15 mars ~17h, heure française = UTC+1 → 16h UTC)
    DEFI_START = "2026-03-10T11:00:00+00:00"
    DEFI_END   = "2026-03-15T11:00:00+00:00"
    defi_teams = db.get_team_period_delta(DEFI_START, DEFI_END)
    defi_teams = [t for t in defi_teams if t.get("team_slug") in _config_slugs]
    top20_defi = defi_teams[:20]
    rows10 = ""
    for i, t in enumerate(top20_defi, 1):
        logo_td = _img(t.get("logo_url", ""), "32")
        medal_td = _medal(i) if i <= 3 else '<span style="color:#888;font-size:.9em">' + str(i) + '</span>'
        rows10 += (
            '<tr>'
            '<td style="text-align:center;font-size:1.2em;width:36px">' + medal_td + '</td>'
            '<td>' + logo_td + '</td>'
            '<td style="font-weight:700">' + t.get("team_name", "") + '</td>'
            '<td style="color:#f1c40f;font-weight:700">+' + _fmt(t.get("delta_period", 0)) + '</td>'
            '</tr>'
        )
    if rows10:
        card10_body = (
            '<p style="color:#888;font-size:.9em;margin-bottom:12px">Du mar. 10/03 midi au dim. 15/03 midi</p>'
            '<table class="rank-table">'
            '<thead><tr><th>#</th><th></th><th>Equipe</th><th>Collecté</th></tr></thead>'
            '<tbody>' + rows10 + '</tbody></table>'
        )
    else:
        card10_body = '<p style="color:#888;text-align:center;padding:24px">Données non encore disponibles pour cette période.</p>'

    if recent_dons:
        don_items = ""
        for d in recent_dons:
            amt = _fmt(d["don_amount"])
            name = d["display_name"]
            if d.get("source") == "skier" and d.get("team_name"):
                name += " (" + d["team_name"] + ")"
            date_str = _fmt_don_date(d["scraped_at"])
            don_items += (
                '<div class="don-item">'
                '<span class="don-amount">+' + amt + '</span>'
                ' pour ' + name + ' — ' + date_str
                + '</div>'
            )
    else:
        don_items = '<div class="don-item don-empty">En attente des premiers dons...</div>'

    sidebar_html = (
        '<div class="sidebar">'
        '<div class="sidebar-title">🔔 Derniers dons détectés</div>'
        + don_items + '</div>'
    )

    footer = (
        '<div class="footer">'
        '<div class="footer-meta">Données mises à jour le ' + generated_at + '</div>'
        '</div>'
    )

    css = (
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{background:#f5f7fa;color:#1a1d2e;font-family:'Barlow Condensed',sans-serif;padding:24px}"
        ".main-content{margin-right:316px}"
        "h1{text-align:center;font-size:2.4em;color:#6c63ff;margin-bottom:8px}"
        ".subtitle{text-align:center;color:#666;margin-bottom:16px}"
        ".global-banner{background:#fff;border:1px solid #e0e4ed;border-radius:16px;padding:20px 24px;"
            "max-width:800px;margin:0 auto 32px;font-size:1.4em;font-weight:700;color:#2c3e50;"
            "text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.06)}"
        ".global-amount{color:#48cfad;font-weight:900}"
        ".global-bar{max-width:500px;height:10px;margin:12px auto 8px}"
        ".global-label{font-size:.75em;color:#666;font-weight:400;margin-top:4px}"
        ".card{background:#fff;border:1px solid #e0e4ed;border-radius:16px;padding:24px;"
            "margin-bottom:32px;max-width:800px;margin-left:auto;margin-right:auto;"
            "box-shadow:0 2px 12px rgba(0,0,0,.06)}"
        ".card-header{margin-bottom:16px}"
        ".card-header h2{font-size:1.8em;color:#2c3e50;letter-spacing:.05em}"
        ".card-subtitle{color:#888;font-size:.95em;margin-top:4px}"
        ".card-body{margin-bottom:16px}"
        ".save-btn{display:block;margin:0 auto;background:#6c63ff;color:#fff;border:none;"
            "border-radius:8px;padding:10px 24px;font-size:1em;font-family:inherit;cursor:pointer}"
        ".save-btn:hover{background:#5a52e0}"
        ".team-card{display:inline-flex;flex-direction:column;align-items:center;"
            "background:#f8f9fc;border:1px solid #e0e4ed;border-radius:12px;padding:16px;"
            "margin:6px;vertical-align:top;text-align:center}"
        ".rank-lg{width:100%!important}.rank-md{width:calc(50% - 14px)}.rank-sm{width:calc(33% - 14px)}"
        ".team-rank{font-size:2em;margin-bottom:6px}"
        ".team-name{font-weight:700;font-size:1.1em;margin:6px 0 4px;color:#2c3e50}"
        ".team-amount{font-size:1.6em;color:#48cfad;font-weight:900}"
        ".progress-bar-wrap{background:#e0e4ed;border-radius:4px;height:8px;width:100%;margin:8px 0 4px;overflow:hidden}"
        ".progress-bar{height:100%;background:linear-gradient(90deg,#6c63ff,#48cfad);border-radius:4px}"
        ".progress-label{color:#888;font-size:.85em}"
        ".versus-wrap{display:flex;gap:16px;align-items:flex-start}"
        ".versus-side{flex:1;background:#f8f9fc;border:1px solid #e0e4ed;border-radius:12px;padding:16px}"
        ".versus-center{width:120px;text-align:center;padding-top:24px}"
        ".vs-label{font-size:2em;font-weight:900;color:#f1c40f;margin-bottom:12px}"
        ".side-title{font-size:1.3em;font-weight:700;margin-bottom:8px}"
        ".side-total{font-size:1.8em;font-weight:900;color:#48cfad}"
        ".side-stats{color:#888;font-size:.9em;margin:4px 0 12px}"
        ".dual-bar{background:#e0e4ed;border-radius:4px;height:16px;width:100%;overflow:hidden;display:flex}"
        ".dual-bar-f{height:100%;background:#e91e8c;border-radius:4px 0 0 4px}"
        ".dual-bar-m{height:100%;background:#3498db;border-radius:0 4px 4px 0}"
        ".dual-pcts{margin-top:6px;font-size:1em;font-weight:700}"
        ".logos-mosaic{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px}"
        ".badge-f{background:#e91e8c;color:#fff;border-radius:4px;padding:1px 5px;font-size:.85em}"
        ".badge-m{background:#3498db;color:#fff;border-radius:4px;padding:1px 5px;font-size:.85em}"
        ".duel-wrap{display:flex;gap:12px;align-items:flex-start}"
        ".duel-half{flex:1;background:#f8f9fc;border:1px solid #e0e4ed;border-radius:12px;padding:16px;text-align:center}"
        ".duel-leading{box-shadow:0 0 20px rgba(108,99,255,.3);border:1px solid #6c63ff}"
        ".duel-center{width:100px;text-align:center;padding-top:24px}"
        ".duel-name{font-weight:700;font-size:1.1em;margin:8px 0 4px;color:#2c3e50}"
        ".duel-amount{font-size:1.7em;color:#48cfad;font-weight:900}"
        ".ecart-label{color:#888;font-size:.9em;margin-top:12px}"
        ".ecart-amount{color:#f1c40f;font-weight:900;font-size:1.1em}"
        ".duel-top3{margin-top:12px;text-align:left}"
        ".rank-table{width:100%;border-collapse:collapse}"
        ".rank-table th{color:#888;font-size:.9em;padding:6px 8px;border-bottom:1px solid #e0e4ed;text-align:left}"
        ".rank-table td{padding:8px;border-bottom:1px solid #e0e4ed;vertical-align:middle;color:#1a1d2e}"
        ".rank-table tr:hover td{background:#f5f7fa}"
        ".sidebar{position:fixed;right:0;top:0;width:300px;height:100vh;overflow-y:auto;"
            "background:#fff;border-left:1px solid #e0e4ed;padding:16px;z-index:100}"
        ".sidebar-title{font-size:1em;font-weight:700;color:#2c3e50;margin-bottom:12px;"
            "padding-bottom:8px;border-bottom:1px solid #e0e4ed}"
        ".don-item{padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:.82em;color:#1a1d2e;line-height:1.4}"
        ".don-item:last-child{border-bottom:none}"
        ".don-amount{color:#48cfad;font-weight:700}"
        ".don-empty{color:#888;font-style:italic}"
        ".footer{max-width:800px;margin:0 auto;padding:24px 0;text-align:center;color:#888}"
        ".footer-meta{font-size:.9em}"
        ".skier-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #e0e4ed}"
        ".skier-row:last-child{border-bottom:none}"
        ".skier-top1{background:linear-gradient(90deg,#fffbea,transparent);border-radius:8px;padding:10px}"
        ".skier-rank{font-size:1.3em;min-width:32px}"
        ".skier-photo{border-radius:50%;object-fit:cover}"
        ".skier-name{flex:1;font-weight:700;font-size:1.05em;color:#2c3e50;line-height:1.3}"
        ".skier-team{font-size:.8em;font-weight:400;color:#888;display:block}"
        ".skier-amount{color:#48cfad;font-weight:900;font-size:1.1em}"
        ".skiers-list{}"
        ".skier-gold{background:linear-gradient(90deg,#fffbea,transparent);border-radius:8px;padding:4px}"
        ".obj-summary{margin-top:16px;padding:16px;background:#f8f9fc;border-radius:8px;border:1px solid #e0e4ed}"
        ".obj-summary-row{display:flex;justify-content:space-between;margin-bottom:6px;font-size:1em}"
        "@media(max-width:900px){"
            ".main-content{margin-right:0}"".sidebar{position:static;width:100%;height:auto;border-left:none;border-bottom:1px solid #e0e4ed;margin-bottom:16px}"
            ".versus-wrap,.duel-wrap{flex-direction:column}"
            ".versus-center,.duel-center{width:100%;padding:8px 0}"
            ".rank-md,.rank-sm{width:100%}}"
    )


    js = (
        "function imgToB64(img){return fetch(img.src).then(function(r){return r.blob()}).then(function(blob){return new Promise(function(resolve){var fr=new FileReader();fr.onload=function(){resolve(fr.result)};fr.readAsDataURL(blob)})});}function saveCard(btn,cardId,filename){var el=document.getElementById(cardId);btn.disabled=true;btn.textContent='Traitement...';btn.style.visibility='hidden';var imgs=Array.from(el.querySelectorAll('img'));var origSrcs=imgs.map(function(i){return i.src});Promise.all(imgs.map(function(img){return imgToB64(img).catch(function(){return img.src})})).then(function(b64s){imgs.forEach(function(img,i){img.src=b64s[i]});return new Promise(function(res){requestAnimationFrame(function(){requestAnimationFrame(res)})});}).then(function(){return html2canvas(el,{backgroundColor:'#ffffff',scale:2,useCORS:false,allowTaint:false});}).then(function(canvas){imgs.forEach(function(img,i){img.src=origSrcs[i]});var link=document.createElement('a');link.download=filename;link.href=canvas.toDataURL('image/png');link.click();btn.disabled=false;btn.textContent='📸 Enregistrer';btn.style.visibility='visible';}).catch(function(err){imgs.forEach(function(img,i){img.src=origSrcs[i]});console.error(err);btn.disabled=false;btn.textContent='📸 Enregistrer';btn.style.visibility='visible';})}"

    )

    GF = ("https://fonts.googleapis.com/css2"
          "?family=Barlow+Condensed:wght@400;600;700;900&display=swap")
    H2C = "https://html2canvas.hertzen.com/dist/html2canvas.min.js"

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="fr">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width,initial-scale=1">',
        '  <title>Glisse en Coeur - ' + today.strftime("%d/%m/%Y") + '</title>',
        '  <link href="' + GF + '" rel="stylesheet">',
        '  <script src="' + H2C + '"></script>',
        '  <style>' + css + '</style>',
        "</head>",
        "<body>",
        '  <div class="main-content">',
        '  <h1>🎿 Glisse en Coeur</h1>',
        '  <p class="subtitle">Données du ' + today.strftime("%d/%m/%Y") + '</p>',
        global_banner,
        sidebar_html,
        _card("card5", "DONS DES DERNIÈRES 24H", card5_body,
              "24h-equipes-" + str(today) + ".png", generated_at),
        _card("card8", chr(127942) + " CLASSEMENT DES " + chr(201) + "QUIPES", card8_body,
              "classement-equipes-" + str(today) + ".png", generated_at),
        _card("card4", "DUEL : " + n1 + " vs " + n2, card4_body,
              "duel-" + str(today) + ".png", generated_at),
        _card("card3", DUEL_DEPT_1_NAME.upper() + " " + DUEL_DEPT_1 + " vs " + DUEL_DEPT_2_NAME.upper() + " " + DUEL_DEPT_2, card3_body,
              "depts-" + str(today) + ".png", generated_at),
        _card("card6", "MEILLEURS SKIEURS 24H", card6_body,
              "24h-skieurs-" + str(today) + ".png", generated_at),
        _card("card7", chr(127935) + " TOP 20 SKIEURS", card7_body,
              "top20-skieurs-" + str(today) + ".png", generated_at),
        _card("card9", "&#9792; FILLES vs GARÇONS &#9794;", card9_body,
              "filles-garcons-" + str(today) + ".png", generated_at),
        _card("card10", "&#127942; D" + chr(201) + "FI 1000" + chr(8364), card10_body,
              "defi1000-" + str(today) + ".png", generated_at),
        footer,
        "  </div>",
        '  <script>' + js + '</script>',
        "</body>",
        "</html>",
    ]
    return chr(10).join(html_parts)


@app.route("/")
def index():
    """Génère et retourne le rapport HTML en temps réel."""
    if _HTML_CACHE["html"] is not None:
        return _HTML_CACHE["html"]
    try:
        html = _build_html()
        _HTML_CACHE["html"] = html
        return html
    except Exception as exc:
        log.error("Erreur génération HTML : %s", exc, exc_info=True)
        return (
            "<h2>Glisse en Coeur</h2>"
            "<p>Données en cours de chargement... Revenez dans quelques instants.</p>"
        ), 200


@app.route("/run", methods=["POST"])
def run():
    """Endpoint appelé par Make toutes les 5 minutes."""
    token = request.headers.get("X-Token", "")
    if token != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    def job():
        try:
            from db import init_db
            from scraper import scrape_all
            init_db()
            scrape_all()
            _HTML_CACHE["html"] = None
            log.info("Cache HTML invalide")
        except Exception as exc:
            log.error("Erreur lors du job : %s", exc, exc_info=True)

    threading.Thread(target=job, daemon=True).start()
    return jsonify({"status": "lance", "date": str(date.today())}), 200


@app.route("/admin")
def admin():
    import sqlite3 as _sq
    db_path = "/data/glisse.db"
    db_size = f"{os.path.getsize(db_path) / 1024 / 1024:.2f} MB" if os.path.exists(db_path) else "N/A"

    try:
        con = _sq.connect(db_path)
        con.row_factory = _sq.Row
        team_count = con.execute("SELECT COUNT(*) FROM team_snapshots").fetchone()[0]
        skier_count = con.execute("SELECT COUNT(*) FROM skier_snapshots").fetchone()[0]
        last_teams = con.execute(
            "SELECT team_name, amount, scraped_at FROM team_snapshots ORDER BY scraped_at DESC LIMIT 20"
        ).fetchall()
        last_skiers = con.execute(
            "SELECT first_name, last_name, team_slug, amount, scraped_at "
            "FROM skier_snapshots ORDER BY scraped_at DESC LIMIT 20"
        ).fetchall()
        con.close()
    except Exception as e:
        return f"Erreur DB : {e}", 500

    team_rows = "".join(
        "<tr><td>" + r["team_name"] + "</td>"
        "<td>" + f"{r['amount']:,}" + " €</td>"
        "<td>" + r["scraped_at"] + "</td></tr>"
        for r in last_teams
    )
    skier_rows = "".join(
        "<tr><td>" + r["first_name"] + " " + r["last_name"].upper() + "</td>"
        "<td>" + (r["team_slug"] or "") + "</td>"
        "<td>" + f"{r['amount']:,}" + " €</td>"
        "<td>" + r["scraped_at"] + "</td></tr>"
        for r in last_skiers
    )

    adm_css = (
        "body{font-family:sans-serif;background:#f5f7fa;color:#1a1d2e;padding:24px}"
        "h1,h2{color:#2c3e50;margin-bottom:12px}"
        "h2{margin-top:32px}"
        ".stats{display:flex;gap:16px;margin-bottom:32px;flex-wrap:wrap}"
        ".stat{background:#fff;border:1px solid #e0e4ed;border-radius:8px;padding:16px 24px}"
        ".stat-val{font-size:2em;font-weight:700;color:#6c63ff}"
        ".stat-lbl{color:#888;font-size:.9em}"
        "table{width:100%;border-collapse:collapse;background:#fff;"
            "border:1px solid #e0e4ed;margin-bottom:24px}"
        "th{background:#f0f2f5;padding:8px 12px;text-align:left;color:#666;font-size:.9em}"
        "td{padding:8px 12px;border-bottom:1px solid #e0e4ed;font-size:.9em}"
    )

    html = (
        "<!DOCTYPE html><html lang=\"fr\"><head>"
        "<meta charset=\"UTF-8\">"
        "<title>Admin - Glisse en Coeur</title>"
        "<style>" + adm_css + "</style></head><body>"
        "<h1>Administration — Glisse en Coeur</h1>"
        "<div class=\"stats\">"
        "<div class=\"stat\"><div class=\"stat-val\">" + f"{team_count:,}" + "</div>"
            "<div class=\"stat-lbl\">Snapshots équipes</div></div>"
        "<div class=\"stat\"><div class=\"stat-val\">" + f"{skier_count:,}" + "</div>"
            "<div class=\"stat-lbl\">Snapshots skieurs</div></div>"
        "<div class=\"stat\"><div class=\"stat-val\">" + db_size + "</div>"
            "<div class=\"stat-lbl\">Taille base de données</div></div>"
        "</div>"
        "<h2>20 derniers snapshots équipes</h2>"
        "<table><thead><tr><th>Equipe</th><th>Montant</th><th>Timestamp</th></tr></thead>"
        "<tbody>" + team_rows + "</tbody></table>"
        "<h2>20 derniers snapshots skieurs</h2>"
        "<table><thead><tr><th>Skieur</th><th>Equipe</th><th>Montant</th><th>Timestamp</th></tr></thead>"
        "<tbody>" + skier_rows + "</tbody></table>"
        "</body></html>"
    )
    return html


@app.route("/qr/<slug>")
def qr_team(slug):
    import io
    import base64 as _b64
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    from config import MAIN_URL

    team_cfg = next((t for t in _CONFIG_TEAMS if t["slug"] == slug), None)
    if not team_cfg:
        return "Équipe non trouvée", 404

    team_name = team_cfg["name"]
    donate_url = MAIN_URL + "/faire-un-don/" + slug

    # Logo depuis la DB
    logo_img = None
    logo_data = db.get_team_logo(slug)
    if logo_data:
        try:
            if logo_data.get("logo_base64"):
                b64_data = logo_data["logo_base64"]
                if "base64," in b64_data:
                    b64_data = b64_data.split("base64,", 1)[1]
                logo_img = Image.open(io.BytesIO(_b64.b64decode(b64_data))).convert("RGBA")
            elif logo_data.get("logo_url"):
                import requests as _req
                r = _req.get(logo_data["logo_url"], timeout=5)
                logo_img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception:
            logo_img = None
    if logo_img:
        logo_img.thumbnail((60, 60), Image.LANCZOS)

    # Police
    font_path = None
    for _fp in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.exists(_fp):
            font_path = _fp
            break
    try:
        font_title = ImageFont.truetype(font_path, 22) if font_path else ImageFont.load_default()
    except Exception:
        font_title = ImageFont.load_default()

    # QR code
    qr = qrcode.QRCode(box_size=8, border=3)
    qr.add_data(donate_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1a1d2e", back_color="white").convert("RGBA")
    qr_w, qr_h = qr_img.size

    # Mesure du texte
    padding = 20
    gap = 12
    dummy = Image.new("RGBA", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), team_name, font=font_title)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    logo_w, logo_h = (logo_img.size if logo_img else (0, 0))

    if logo_img:
        header_w = logo_w + gap + text_w
        header_h = max(logo_h, text_h)
    else:
        header_w = text_w
        header_h = text_h

    total_w = max(qr_w + 2 * padding, header_w + 2 * padding)
    total_h = padding + header_h + padding + qr_h + padding

    img = Image.new("RGB", (total_w, total_h), "white")
    draw = ImageDraw.Draw(img)

    # En-tête : logo + nom
    header_x = (total_w - header_w) // 2
    if logo_img:
        logo_y = padding + (header_h - logo_h) // 2
        img.paste(logo_img, (header_x, logo_y), logo_img)
        text_x = header_x + logo_w + gap
    else:
        text_x = header_x
    text_y = padding + (header_h - text_h) // 2 - bbox[1]
    draw.text((text_x, text_y), team_name, font=font_title, fill="#1a1d2e")

    # QR code
    qr_x = (total_w - qr_w) // 2
    qr_y = padding + header_h + padding
    img.paste(qr_img.convert("RGB"), (qr_x, qr_y))

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    from flask import send_file
    return send_file(out, mimetype="image/png", download_name=slug + "-qr.png")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
