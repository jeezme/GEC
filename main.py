import logging
import os
import threading
from datetime import date

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "changeme")

# Create directories at startup
os.makedirs("/data", exist_ok=True)
os.makedirs("reports", exist_ok=True)

log = logging.getLogger(__name__)


@app.route("/")
def index():
    """Sert directement le dernier rapport HTML disponible."""
    reports = (
        sorted(f for f in os.listdir("reports") if f.endswith(".html"))
        if os.path.exists("reports") else []
    )
    if not reports:
        return (
            "<h2>Glisse en Coeur</h2>"
            "<p>Premiere collecte en cours... Revenez dans quelques instants.</p>"
        ), 200
    return send_file(os.path.join("reports", reports[-1]))


@app.route("/run", methods=["POST"])
def run():
    """Endpoint appele par Make toutes les 5 minutes."""
    token = request.headers.get("X-Token", "")
    if token != SECRET_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401

    def job():
        try:
            from db import init_db
            from gender import warn_unknown_genders
            from scraper import scrape_all
            from report import generate_report
            init_db()
            warn_unknown_genders()
            scrape_all()
            generate_report()
        except Exception as exc:
            log.error("Erreur lors du job : %s", exc, exc_info=True)

    threading.Thread(target=job, daemon=True).start()
    return jsonify({"status": "lance", "date": str(date.today())}), 200


@app.route("/rapport/latest")
def latest():
    """Sert le rapport du jour."""
    filename = f"rapport_{date.today()}.html"
    return get_rapport(filename)


@app.route("/rapport/<filename>")
def get_rapport(filename):
    """Sert le fichier HTML du rapport demande."""
    path = os.path.join("reports", filename)
    if not os.path.exists(path):
        return "Rapport non trouve", 404
    return send_file(path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


@app.route("/admin")
def admin():
    token = request.headers.get("X-Token", "")
    if token != SECRET_TOKEN:
        return "Unauthorized", 401

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
