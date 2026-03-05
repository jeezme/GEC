import logging
import os
import threading
from datetime import date

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)
SECRET_TOKEN = os.environ.get("SECRET_TOKEN", "changeme")

# Create directories at startup
os.makedirs("data", exist_ok=True)
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
