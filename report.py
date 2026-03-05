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


def _gender_badge(g: str) -> str:
    if g == "F":
        return '<span class="badge-f">&#9792;</span>'
    return '<span class="badge-f">&#9794;</span>'


def _img(src: str, width: str, extra: str = "") -> str:
    if not src:
        return ""
    return f'<img src="{src}" width="{width}"{extra} onerror="this.remove()">' 


def _team_card_html(team: dict, rank: int, size: str = "md") -> str:
    pct = _pct(team.get("amount", 0), team.get("objectif", 1) or 1)
    logo = team.get("logo_url", "")
    logo_size = {"lg": "100", "md": "64", "sm": "40"}.get(size, "64")
    gold = (' style="background:linear-gradient(135deg,#2d2500 0%,#1a1d2e 60%);border-color:#f1c40f"' 
            if rank == 1 else "")
    return f"""
    <div class="team-card rank-{size}"{gold}>
      <div class="team-rank">{_medal(rank)}</div>
      {_img(logo, logo_size)}
      <div class="team-name">{team.get("team_name", "")}</div>
      <div class="team-amount">{_fmt(team.get("amount", 0))}</div>
      <div class="progress-bar-wrap">
        <div class="progress-bar" style="width:{pct}%"></div>
      </div>
      <div class="progress-label">{pct}% de l'objectif ({_fmt(team.get("objectif", 0))})</div>
    </div>"""


def _skier_row_html(skier: dict, rank: int, show_delta: bool = False) -> str:
    photo = skier.get("photo_url", "")
    first = skier.get("first_name", "")
    last = skier.get("last_name", "").upper()
    name = f"{first} {last}".strip()
    amount = (skier.get("delta_24h", skier.get("amount", 0))
              if show_delta else skier.get("amount", 0))
    gender = skier.get("gender", "M")
    badge = '<span class="badge-f">&#9792;</span>' if gender == "F" else '<span class="badge-m">&#9794;</span>'
    big = rank == 1 and show_delta
    sz = "56" if big else "40"
    cls = "skier-row skier-top1" if big else "skier-row"
    return f"""
    <div class="{cls}">
      <span class="skier-rank">{_medal(rank)}</span>
      {_img(photo, sz, ' class="skier-photo"')}
      <span class="skier-name">{name}</span>
      {badge}
      <span class="skier-amount">{_fmt(amount)}</span>
    </div>"""


def _save_btn(card_id: str, filename: str) -> str:
    return f"""
    <button class="save-btn" onclick="saveCard(this,'{card_id}','{filename}')">
      📸 Enregistrer l'image
    </button>"""


def _card(cid: str, title: str, body: str, save_filename: str, generated_at: str) -> str:
    return f"""
<div class="card" id="{cid}">
  <div class="card-header">
    <h2>{title}</h2>
    <div class="card-subtitle">Genere le {generated_at}</div>
  </div>
  <div class="card-body">{body}</div>
  {_save_btn(cid, save_filename)}
</div>"""


def generate_report():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = date.today()
    out_path = os.path.join(REPORTS_DIR, f"rapport_{today}.html")
    yesterday = today - timedelta(days=1)
    prev_file = f"rapport_{yesterday}.html"
    prev_link = (
        f'<a href="/rapport/{prev_file}">Rapport du {yesterday}</a>'
        if os.path.exists(os.path.join(REPORTS_DIR, prev_file)) else ""
    )
    since_iso = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    generated_at = datetime.now().strftime("%d/%m/%Y à %H:%M")

    teams = db.get_all_latest_teams()
    skiers = db.get_all_latest_skiers()
    teams_delta = db.get_team_24h_delta(since_iso)
    skiers_delta = db.get_skiers_24h_delta(since_iso)

    total_dons = 0
    total_objectif = 1
    try:
        import sqlite3
        con = sqlite3.connect(os.path.join("data", "glisse.db"))
        con.row_factory = sqlite3.Row
        g = con.execute(
            "SELECT total_dons, total_objectif FROM global_snapshots"
            " ORDER BY scraped_at DESC LIMIT 1"
        ).fetchone()
        if g:
            total_dons = g["total_dons"]
            total_objectif = g["total_objectif"] or 1
        con.close()
    except Exception:
        pass

    # CARD 1 - Top 5 equipes
    top5 = teams[:5]
    card1_body = ""
    for i, t in enumerate(top5, 1):
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
        '<div class="versus-side side-f">'
        '<div class="side-title" style="color:#e91e8c">&#9792; FILLES</div>'
        f'<div class="side-total">{_fmt(total_f)}</div>'
        f'<div class="side-stats">{len(girls)} skieuses &bull; moy. {_fmt(avg_f)}</div>'
        f'<div class="top3">{top3_f}</div></div>'
        '<div class="versus-center">'
        '<div class="vs-label">VS</div>'
        '<div class="dual-bar">'
        f'<div class="dual-bar-f" style="width:{pct_f}%"></div>'
        f'<div class="dual-bar-m" style="width:{pct_m}%"></div>'
        '</div>'
        f'<div class="dual-pcts">'
        f'<span style="color:#e91e8c">{pct_f}%</span> / '
        f'<span style="color:#3498db">{pct_m}%</span></div></div>'
        '<div class="versus-side side-m">'
        '<div class="side-title" style="color:#3498db">&#9794; GARCONS</div>'
        f'<div class="side-total">{_fmt(total_m)}</div>'
        f'<div class="side-stats">{len(boys)} skieurs &bull; moy. {_fmt(avg_m)}</div>'
        f'<div class="top3">{top3_m}</div></div></div>'
    )

    # CARD 3 - Savoie 73 vs Haute-Savoie 74
    teams_73 = [t for t in teams if t.get("dept") == "73"]
    teams_74 = [t for t in teams if t.get("dept") == "74"]
    total_73 = sum(t["amount"] for t in teams_73)
    total_74 = sum(t["amount"] for t in teams_74)
    total_depts = total_73 + total_74 or 1
    pct_73 = _pct(total_73, total_depts)
    pct_74 = _pct(total_74, total_depts)
    logos_73 = "".join(_img(t.get("logo_url", ""), "32", f' title="{t["team_name"]}"')               for t in teams_73 if t.get("logo_url"))
    logos_74 = "".join(_img(t.get("logo_url", ""), "32", f' title="{t["team_name"]}"')               for t in teams_74 if t.get("logo_url"))
    card3_body = (
        '<div class="versus-wrap">'
        '<div class="versus-side side-73">'
        '<div class="side-title" style="color:#e67e22">73 SAVOIE</div>'
        f'<div class="side-total">{_fmt(total_73)}</div>'
        f'<div class="side-stats">{len(teams_73)} équipes</div>'
        f'<div class="logos-mosaic">{logos_73}</div></div>'
        '<div class="versus-center">'
        '<div class="vs-label">VS</div>'
        '<div class="dual-bar">'
        f'<div style="height:100%;width:{pct_73}%;background:#e67e22;display:inline-block;border-radius:4px 0 0 4px"></div>'
        f'<div style="height:100%;width:{pct_74}%;background:#27ae60;display:inline-block;border-radius:0 4px 4px 0"></div>'
        '</div>'
        f'<div class="dual-pcts">'
        f'<span style="color:#e67e22">{pct_73}%</span> / '
        f'<span style="color:#27ae60">{pct_74}%</span></div></div>'
        '<div class="versus-side side-74">'
        '<div class="side-title" style="color:#27ae60">74 HAUTE-SAVOIE</div>'
        f'<div class="side-total">{_fmt(total_74)}</div>'
        f'<div class="side-stats">{len(teams_74)} équipes</div>'
        f'<div class="logos-mosaic">{logos_74}</div></div></div>'
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
        name = team.get("team_name", "")
        amt = _fmt(team.get("amount", 0))
        return (
            f'<div class="duel-half{glow}">{logo_img}'
            f'<div class="duel-name">{name}</div>'
            f'<div class="duel-amount">{amt}</div>'
            f'<div class="progress-bar-wrap"><div class="progress-bar" style="width:{pct}%"></div></div>'
            f'<div class="progress-label">{pct}% objectif</div>'
            f'<div class="duel-top3">{top3}</div></div>'
        )

    card4_body = (
        '<div class="duel-wrap">'
        + _duel_half(team1, skiers1, leading1)
        + f'<div class="duel-center">'
          f'<div class="vs-label">⚔️</div>'
          f'<div class="ecart-label">Ecart</div>'
          f'<div class="ecart-amount">{_fmt(ecart)}</div></div>'
        + _duel_half(team2, skiers2, not leading1)
        + '</div>'
    )

    # CARD 5 - Dons 24h par equipe
    top10_teams = teams_delta[:10]
    teams_by_slug = {t["team_slug"]: t for t in teams}
    rows5 = ""
    for i, d in enumerate(top10_teams, 1):
        t5 = teams_by_slug.get(d["team_slug"], {})
        logo_img = _img(t5.get("logo_url", ""), "32")
        trend = "↑" if d["delta_24h"] > 0 else "→"
        tc = "#48cfad" if d["delta_24h"] > 0 else "#aaa"
        rows5 += (
            f'<tr><td>{_medal(i)}</td><td>{logo_img}</td>'
            f'<td>{t5.get("team_name", d["team_slug"])}</td>'
            f'<td style="color:#48cfad;font-weight:700">+{_fmt(d["delta_24h"])}</td>'
            f'<td>{_fmt(d["amount"])}</td>'
            f'<td style="color:{tc};font-size:1.3em">{trend}</td></tr>'
        )
    card5_body = (
        '<table class="rank-table">'
        '<thead><tr><th>Rang</th><th></th><th>Equipe</th><th>+24h</th><th>Total</th><th></th></tr></thead>'
        f'<tbody>{rows5}</tbody></table>'
    )

    # CARD 6 - Top 10 skieurs 24h
    top10_sk = skiers_delta[:10]
    rows6 = "".join(_skier_row_html(s, i + 1, show_delta=True) for i, s in enumerate(top10_sk))
    card6_body = f'<div class="skiers-list">{rows6}</div>'

    # Footer
    pct_global = _pct(total_dons, total_objectif)
    footer = (
        '<div class="footer">'
        '<div class="footer-total">'
        '<span>Cagnotte totale</span>'
        f'<span class="footer-amount">{_fmt(total_dons)}</span>'
        f'<span>/ {_fmt(total_objectif)}</span></div>'
        '<div class="progress-bar-wrap footer-bar">'
        f'<div class="progress-bar" style="width:{pct_global}%"></div></div>'
        f'<div class="footer-meta">Rapport genere le {generated_at} {prev_link}</div></div>'
    )


    css = (
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{background:#0f1020;color:#fff;font-family:'Barlow Condensed',sans-serif;padding:24px}"
        "h1{text-align:center;font-size:2.4em;color:#6c63ff;margin-bottom:8px}"
        ".subtitle{text-align:center;color:#aaa;margin-bottom:32px}"
        ".card{background:#1a1d2e;border:1px solid #2a2d3e;border-radius:16px;padding:24px;"
            "margin-bottom:32px;max-width:800px;margin-left:auto;margin-right:auto}"
        ".card-header{margin-bottom:16px}"
        ".card-header h2{font-size:1.8em;color:#6c63ff;letter-spacing:.05em}"
        ".card-subtitle{color:#888;font-size:.95em;margin-top:4px}"
        ".card-body{margin-bottom:16px}"
        ".save-btn{display:block;margin:0 auto;background:#6c63ff;color:#fff;border:none;"
            "border-radius:8px;padding:10px 24px;font-size:1em;font-family:inherit;cursor:pointer}"
        ".save-btn:hover{background:#5a52e0}"
        ".team-card{display:inline-flex;flex-direction:column;align-items:center;"
            "background:#22253a;border:1px solid #333;border-radius:12px;padding:16px;"
            "margin:6px;vertical-align:top;text-align:center}"
        ".rank-lg{width:100%!important}"
        ".rank-md{width:calc(50% - 14px)}"
        ".rank-sm{width:calc(33% - 14px)}"
        ".team-rank{font-size:2em;margin-bottom:6px}"
        ".team-name{font-weight:700;font-size:1.1em;margin:6px 0 4px}"
        ".team-amount{font-size:1.6em;color:#48cfad;font-weight:900}"
        ".progress-bar-wrap{background:#333;border-radius:4px;height:8px;"
            "width:100%;margin:8px 0 4px;overflow:hidden}"
        ".progress-bar{height:100%;background:linear-gradient(90deg,#6c63ff,#48cfad);border-radius:4px}"
        ".progress-label{color:#888;font-size:.85em}"
        ".versus-wrap{display:flex;gap:16px;align-items:flex-start}"
        ".versus-side{flex:1;background:#22253a;border-radius:12px;padding:16px}"
        ".versus-center{width:120px;text-align:center;padding-top:24px}"
        ".vs-label{font-size:2em;font-weight:900;color:#f1c40f;margin-bottom:12px}"
        ".side-title{font-size:1.3em;font-weight:700;margin-bottom:8px}"
        ".side-total{font-size:1.8em;font-weight:900;color:#48cfad}"
        ".side-stats{color:#888;font-size:.9em;margin:4px 0 12px}"
        ".dual-bar{background:#333;border-radius:4px;height:16px;width:100%;overflow:hidden;display:flex}"
        ".dual-bar-f{height:100%;background:#e91e8c;border-radius:4px 0 0 4px}"
        ".dual-bar-m{height:100%;background:#3498db;border-radius:0 4px 4px 0}"
        ".dual-pcts{margin-top:6px;font-size:1em;font-weight:700}"
        ".logos-mosaic{display:flex;flex-wrap:wrap;gap:4px;margin-top:12px}"
        ".skier-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #2a2d3e}"
        ".skier-row:last-child{border-bottom:none}"
        ".skier-top1{background:linear-gradient(90deg,#2d2500,transparent);border-radius:8px;padding:10px}"
        ".skier-rank{font-size:1.3em;min-width:32px}"
        ".skier-photo{border-radius:50%;object-fit:cover}"
        ".skier-name{flex:1;font-weight:700;font-size:1.05em}"
        ".skier-amount{color:#48cfad;font-weight:900;font-size:1.1em}"
        ".badge-f{background:#e91e8c;color:#fff;border-radius:4px;padding:1px 5px;font-size:.85em}"
        ".badge-m{background:#3498db;color:#fff;border-radius:4px;padding:1px 5px;font-size:.85em}"
        ".duel-wrap{display:flex;gap:12px;align-items:flex-start}"
        ".duel-half{flex:1;background:#22253a;border-radius:12px;padding:16px;text-align:center}"
        ".duel-leading{box-shadow:0 0 20px rgba(108,99,255,.4);border:1px solid #6c63ff}"
        ".duel-center{width:100px;text-align:center;padding-top:24px}"
        ".duel-name{font-weight:700;font-size:1.1em;margin:8px 0 4px}"
        ".duel-amount{font-size:1.7em;color:#48cfad;font-weight:900}"
        ".ecart-label{color:#888;font-size:.9em;margin-top:12px}"
        ".ecart-amount{color:#f1c40f;font-weight:900;font-size:1.1em}"
        ".duel-top3{margin-top:12px;text-align:left}"
        ".rank-table{width:100%;border-collapse:collapse}"
        ".rank-table th{color:#888;font-size:.9em;padding:6px 8px;border-bottom:1px solid #333;text-align:left}"
        ".rank-table td{padding:8px;border-bottom:1px solid #2a2d3e;vertical-align:middle}"
        ".rank-table tr:hover td{background:#22253a}"
        ".footer{max-width:800px;margin:0 auto;padding:24px 0;text-align:center;color:#888}"
        ".footer-total{font-size:1.3em;margin-bottom:8px;display:flex;"
            "justify-content:center;gap:8px;align-items:center}"
        ".footer-amount{color:#48cfad;font-weight:900;font-size:1.2em}"
        ".footer-bar{max-width:600px;margin:0 auto 12px}"
        ".footer-meta{font-size:.9em;margin-top:8px}"
        ".footer-meta a{color:#6c63ff}"
        ".skiers-list{max-height:600px}"
        ".top3 .skier-row{padding:4px 0}"
        "@media(max-width:600px){"
            ".versus-wrap,.duel-wrap{flex-direction:column}"
            ".versus-center,.duel-center{width:100%;padding:8px 0}"
            ".rank-md,.rank-sm{width:100%}}"
    )


    js = (
        "function saveCard(btn,cardId,filename){"
        "var el=document.getElementById(cardId);"
        "btn.disabled=true;"
        "btn.textContent='Traitement...';"
        "html2canvas(el,{backgroundColor:'#1a1d2e',scale:2,useCORS:true,allowTaint:true})"
        ".then(function(canvas){"
        "var link=document.createElement('a');"
        "link.download=filename;"
        "link.href=canvas.toDataURL('image/png');"
        "link.click();"
        "btn.disabled=false;"
        "btn.textContent='📸 Enregistrer';"
        "}).catch(function(err){"
        "console.error(err);"
        "btn.disabled=false;"
        "btn.textContent='📸 Enregistrer';"
        "});}"
    )

    GF = ("https://fonts.googleapis.com/css2"
          "?family=Barlow+Condensed:wght@400;600;700;900&display=swap")
    H2C = "https://html2canvas.hertzen.com/dist/html2canvas.min.js"
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"fr\">",
        "<head>",
        "  <meta charset=\"UTF-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        f"  <title>Glisse en Coeur - Rapport {today}</title>",
        f'  <link href="{GF}" rel="stylesheet">',
        f'  <script src="{H2C}"></script>',
        f"  <style>{css}</style>",
        "</head>",
        "<body>",
        "  <h1>🎿 Glisse en Coeur</h1>",
        f"  <p class=\"subtitle\">Rapport du {today.strftime('%d/%m/%Y')}</p>",
        _card("card1", "🏆 CLASSEMENT EQUIPES", card1_body,
              f"top5-equipes-{today}.png", generated_at),
        _card("card2", "⚡ FILLES vs GARCONS", card2_body,
              f"filles-garcons-{today}.png", generated_at),
        _card("card3", "🗺️ SAVOIE 73 vs HAUTE-SAVOIE 74", card3_body,
              f"depts-{today}.png", generated_at),
        _card("card4", f"⚔️ DUEL : {n1} vs {n2}", card4_body,
              f"duel-{today}.png", generated_at),
        _card("card5", "🕐 DONS DES DERNIERES 24H", card5_body,
              f"24h-equipes-{today}.png", generated_at),
        _card("card6", "🎿 MEILLEURS SKIEURS 24H", card6_body,
              f"24h-skieurs-{today}.png", generated_at),
        footer,
        f"  <script>{js}</script>",
        "</body>",
        "</html>",
    ]
    html = chr(10).join(html_parts)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    log.info("Rapport genere : %s", out_path)
    return out_path
