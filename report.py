import logging
import os
from datetime import date, datetime, timedelta, timezone

import db
from config import DUEL_TEAM_1, DUEL_TEAM_2

log = logging.getLogger(__name__)
REPORTS_DIR = "reports"
NBSP = " "
EURO = "€"


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", NBSP) + NBSP + EURO


def _pct(a: int, b: int) -> float:
    return round(min(a / b * 100, 100), 1) if b else 0.0


def _medal(rank: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(rank, f"#{rank}")


def _img(src: str, width: str, extra: str = "") -> str:
    if not src:
        return ""
    return '<img src="' + src + '" width="' + width + '"' + extra + ' onerror="this.remove()">'


def _team_card_html(team: dict, rank: int, size: str = "md") -> str:
    pct = _pct(team.get("amount", 0), team.get("objectif", 1) or 1)
    logo = team.get("logo_base64") or team.get("logo_url", "")
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


def _skier_row_html(skier: dict, rank: int, show_delta: bool = False,
                    show_badge: bool = True, show_team: bool = False) -> str:
    photo = skier.get("photo_base64") or skier.get("photo_url", "")
    first = skier.get("first_name", "")
    last = skier.get("last_name", "").upper()
    name = (first + " " + last).strip()
    team_name = skier.get("team_name", "")
    amount = (skier.get("delta_24h", skier.get("amount", 0))
              if show_delta else skier.get("amount", 0))
    gender = skier.get("gender", "M")
    badge = (
        '<span class="badge-f">&#9792;</span>'
        if gender == "F"
        else '<span class="badge-m">&#9794;</span>'
    )
    big = rank == 1 and show_delta
    sz = "56" if big else "40"
    cls = "skier-row skier-top1" if big else "skier-row"
    team_span = (
        '<br><span class="skier-team">' + team_name + '</span>'
        if show_team and team_name else ""
    )
    photo_html = _img(photo, sz, ' class="skier-photo"')
    return (
        '<div class="' + cls + '">'
        '<span class="skier-rank">' + _medal(rank) + '</span>'
        + photo_html
        + '<span class="skier-name">' + name + team_span + '</span>'
        + (badge if show_badge else "")
        + '<span class="skier-amount">' + _fmt(amount) + '</span>'
        '</div>'
    )


def _save_btn(card_id: str, filename: str) -> str:
    ap = chr(39)
    return (
        '<button class="save-btn" onclick="saveCard(this,' + ap + card_id + ap + ',' + ap + filename + ap + ')">' +
        chr(128248) + ' Enregistrer l' + ap + 'image</button>'
    )


def _card(cid: str, title: str, body: str, save_filename: str, generated_at: str) -> str:
    return (
        '<div class="card" id="' + cid + '">'
        '<div class="card-header">'
        '<h2>' + title + '</h2>'
        '<div class="card-subtitle">Généré le ' + generated_at + '</div>'
        '</div>'
        '<div class="card-body">' + body + '</div>'
        + _save_btn(cid, save_filename)
        + '</div>'
    )


def _fmt_don_date(scraped_at: str) -> str:
    try:
        dt = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        months = ["jan", "fév", "mars", "avr", "mai", "juin",
                  "juil", "août", "sep", "oct", "nov", "déc"]
        return f"{dt.day:02d} {months[dt.month - 1]} à {dt.hour:02d}h{dt.minute:02d}"
    except Exception:
        return scraped_at


def generate_report():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = date.today()
    out_path = os.path.join(REPORTS_DIR, f"rapport_{today}.html")
    yesterday = today - timedelta(days=1)
    prev_file = f"rapport_{yesterday}.html"
    prev_link = (
        '<a href="/rapport/' + prev_file + '">Rapport du ' + str(yesterday) + '</a>'
        if os.path.exists(os.path.join(REPORTS_DIR, prev_file)) else ""
    )
    generated_at = datetime.now().strftime("%d/%m/%Y à %H:%M")

    teams = db.get_all_latest_teams()
    skiers = db.get_all_latest_skiers()
    teams_delta = db.get_team_24h_delta()
    skiers_delta = db.get_skiers_24h_delta()
    recent_dons = db.get_recent_dons(20)
    teams_by_slug = {t["team_slug"]: t for t in teams}

    total_dons = 0
    total_objectif = 1
    try:
        import sqlite3
        con = sqlite3.connect("/data/glisse.db")
        con.row_factory = sqlite3.Row
        g = con.execute(
            "SELECT total_dons, total_objectif FROM global_snapshots ORDER BY scraped_at DESC LIMIT 1"
        ).fetchone()
        if g:
            total_dons = g["total_dons"]
            total_objectif = g["total_objectif"] or 1
        con.close()
    except Exception:
        pass

    pct_global = _pct(total_dons, total_objectif)
    global_banner = (
        '<div class="global-banner">'
        '🎿 Cagnotte totale : '
        '<span class="global-amount">' + _fmt(total_dons) + '</span>'
        ' / ' + _fmt(total_objectif)
        + '<div class="progress-bar-wrap global-bar">'
        '<div class="progress-bar" style="width:' + str(pct_global) + '%"></div></div>'
        '<div class="global-label">' + str(pct_global) + "% de l'objectif</div>"
        '</div>'
    )

    # CARD 1 - Top 6 equipes
    top6 = teams[:6]
    card1_body = ""
    for i, t in enumerate(top6, 1):
        size = "lg" if i == 1 else ("md" if i <= 3 else "sm")
        card1_body += _team_card_html(t, i, size)

    # CARD 2 - Filles vs Garcons
    girls = [s for s in skiers if s.get("gender") == "F"]
    boys  = [s for s in skiers if s.get("gender") == "M"]
    total_f = sum(s["amount"] for s in girls)
    total_m = sum(s["amount"] for s in boys)
    total_gm = total_f + total_m or 1
    pct_f = _pct(total_f, total_gm)
    pct_m = _pct(total_m, total_gm)
    avg_f = total_f // len(girls) if girls else 0
    avg_m = total_m // len(boys) if boys else 0
    top3_f = "".join(_skier_row_html(s, i + 1) for i, s in enumerate(girls[:3]))
    top3_m = "".join(_skier_row_html(s, i + 1) for i, s in enumerate(boys[:3]))
    card2_body = (
        '<div class="versus-wrap">'
        '<div class="versus-side">'
        '<div class="side-title" style="color:#e91e8c">&#9792; FILLES</div>'
        '<div class="side-total">' + _fmt(total_f) + '</div>'
        '<div class="side-stats">' + str(len(girls)) + ' skieuses &bull; moy. ' + _fmt(avg_f) + '</div>'
        '<div class="top3">' + top3_f + '</div></div>'
        '<div class="versus-center"><div class="vs-label">VS</div>'
        '<div class="dual-bar">'
        '<div class="dual-bar-f" style="width:' + str(pct_f) + '%"></div>'
        '<div class="dual-bar-m" style="width:' + str(pct_m) + '%"></div>'
        '</div>'
        '<div class="dual-pcts">'
        '<span style="color:#e91e8c">' + str(pct_f) + '%</span> / '
        '<span style="color:#3498db">' + str(pct_m) + '%</span></div></div>'
        '<div class="versus-side">'
        '<div class="side-title" style="color:#3498db">&#9794; GARCONS</div>'
        '<div class="side-total">' + _fmt(total_m) + '</div>'
        '<div class="side-stats">' + str(len(boys)) + ' skieurs &bull; moy. ' + _fmt(avg_m) + '</div>'
        '<div class="top3">' + top3_m + '</div></div></div>'
    )


    # CARD 3 - Savoie 73 vs Haute-Savoie 74
    teams_73 = [t for t in teams if t.get("dept") == "73"]
    teams_74 = [t for t in teams if t.get("dept") == "74"]
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
        '<div class="side-title" style="color:#e67e22">73 SAVOIE</div>'
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
        '<div class="side-title" style="color:#27ae60">74 HAUTE-SAVOIE</div>'
        '<div class="side-total">' + _fmt(total_74) + '</div>'
        '<div class="side-stats">' + str(len(teams_74)) + ' équipes</div>'
        '<div class="logos-mosaic">' + logos_74 + '</div></div></div>'
    )

    # CARD 4 - Duel
    team1 = next((t for t in teams if t["team_slug"] == DUEL_TEAM_1), None)
    team2 = next((t for t in teams if t["team_slug"] == DUEL_TEAM_2), None)
    a1 = team1["amount"] if team1 else 0
    a2 = team2["amount"] if team2 else 0
    ecart = abs(a1 - a2)
    leading1 = a1 >= a2
    skiers1 = sorted([s for s in skiers if s.get("team_slug") == DUEL_TEAM_1],
                     key=lambda x: x["amount"], reverse=True)
    skiers2 = sorted([s for s in skiers if s.get("team_slug") == DUEL_TEAM_2],
                     key=lambda x: x["amount"], reverse=True)
    n1 = team1["team_name"] if team1 else DUEL_TEAM_1
    n2 = team2["team_name"] if team2 else DUEL_TEAM_2

    def _duel_half(team, side_skiers, leading):
        if not team:
            return '<div class="duel-half">Equipe introuvable</div>'
        pct = _pct(team["amount"], team.get("objectif", 1) or 1)
        glow = " duel-leading" if leading else ""
        top3 = "".join(_skier_row_html(s, i + 1) for i, s in enumerate(side_skiers[:3]))
        logo_img = _img(team.get("logo_url", ""), "80")
        return (
            '<div class="duel-half' + glow + '">' + logo_img
            + '<div class="duel-name">' + team.get("team_name", "") + '</div>'
            '<div class="duel-amount">' + _fmt(team.get("amount", 0)) + '</div>'
            '<div class="progress-bar-wrap">'
            '<div class="progress-bar" style="width:' + str(pct) + '%"></div></div>'
            '<div class="progress-label">' + str(pct) + '% objectif</div>'
            '<div class="duel-top3">' + top3 + '</div></div>'
        )

    card4_body = (
        '<div class="duel-wrap">'
        + _duel_half(team1, skiers1, leading1)
        + '<div class="duel-center">'
          '<div class="vs-label">⚔️</div>'
          '<div class="ecart-label">Ecart</div>'
          '<div class="ecart-amount">' + _fmt(ecart) + '</div></div>'
        + _duel_half(team2, skiers2, not leading1)
        + '</div>'
    )


    # CARD 5 - Dons 24h par equipe (trie par delta_24h desc)
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

    # CARD 6 - Top 10 skieurs 24h (trie par delta_24h desc, sans badge, avec equipe)
    top10_sk = skiers_delta[:10]
    for s in top10_sk:
        s["team_name"] = teams_by_slug.get(s.get("team_slug", ""), {}).get("team_name", "")
    rows6 = "".join(
        _skier_row_html(s, i + 1, show_delta=True, show_badge=False, show_team=True)
        for i, s in enumerate(top10_sk)
    )
    card6_body = '<div class="skiers-list">' + rows6 + '</div>'

    # SIDEBAR - 20 derniers dons detectes
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

    # Footer
    footer = (
        '<div class="footer">'
        '<div class="footer-meta">Rapport généré le '
        + generated_at + ' ' + prev_link + '</div></div>'
    )


    # CSS - theme clair
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
        ".skier-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #e0e4ed}"
        ".skier-row:last-child{border-bottom:none}"
        ".skier-top1{background:linear-gradient(90deg,#fffbea,transparent);border-radius:8px;padding:10px}"
        ".skier-rank{font-size:1.3em;min-width:32px}"
        ".skier-photo{border-radius:50%;object-fit:cover}"
        ".skier-name{flex:1;font-weight:700;font-size:1.05em;color:#2c3e50;line-height:1.3}"
        ".skier-team{font-size:.8em;font-weight:400;color:#888;display:block}"
        ".skier-amount{color:#48cfad;font-weight:900;font-size:1.1em}"
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
        ".footer-meta{font-size:.9em}.footer-meta a{color:#6c63ff}"
        ".skiers-list{max-height:600px}.top3 .skier-row{padding:4px 0}"
        "@media(max-width:900px){"
            ".main-content{margin-right:0}.sidebar{display:none}"
            ".versus-wrap,.duel-wrap{flex-direction:column}"
            ".versus-center,.duel-center{width:100%;padding:8px 0}"
            ".rank-md,.rank-sm{width:100%}}"
    )


    js = (
        "function saveCard(btn,cardId,filename){"
        "var el=document.getElementById(cardId);"
        "btn.disabled=true;btn.textContent='Traitement...';"
        "html2canvas(el,{backgroundColor:'#ffffff',scale:2,useCORS:true,allowTaint:true})"
        ".then(function(canvas){"
        "var link=document.createElement('a');"
        "link.download=filename;link.href=canvas.toDataURL('image/png');link.click();"
        "btn.disabled=false;btn.textContent='📸 Enregistrer';"
        "}).catch(function(err){"
        "console.error(err);btn.disabled=false;btn.textContent='📸 Enregistrer';"
        "});}"
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
        '  <title>Glisse en Coeur - Rapport ' + str(today) + '</title>',
        '  <link href="' + GF + '" rel="stylesheet">',
        '  <script src="' + H2C + '"></script>',
        '  <style>' + css + '</style>',
        "</head>",
        "<body>",
        sidebar_html,
        '  <div class="main-content">',
        '  <h1>🎿 Glisse en Coeur</h1>',
        '  <p class="subtitle">Rapport du ' + today.strftime("%d/%m/%Y") + '</p>',
        global_banner,
        _card("card1", "🏆 CLASSEMENT ÉQUIPES", card1_body,
              "top6-equipes-" + str(today) + ".png", generated_at),
        _card("card2", "⚡ FILLES vs GARCONS", card2_body,
              "filles-garcons-" + str(today) + ".png", generated_at),
        _card("card3", "🗺️ SAVOIE 73 vs HAUTE-SAVOIE 74", card3_body,
              "depts-" + str(today) + ".png", generated_at),
        _card("card4", "⚔️ DUEL : " + n1 + " vs " + n2, card4_body,
              "duel-" + str(today) + ".png", generated_at),
        _card("card5", "🕐 DONS DES DERNIÈRES 24H", card5_body,
              "24h-equipes-" + str(today) + ".png", generated_at),
        _card("card6", "🎿 MEILLEURS SKIEURS 24H", card6_body,
              "24h-skieurs-" + str(today) + ".png", generated_at),
        footer,
        "  </div>",
        '  <script>' + js + '</script>',
        "</body>",
        "</html>",
    ]
    html = chr(10).join(html_parts)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("Rapport genere : %s", out_path)
    return out_path
