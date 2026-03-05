import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "glisse.db")


def _conn():
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """Cree les tables si elles n'existent pas."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS global_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_dons INTEGER,
                total_objectif INTEGER,
                scraped_at TEXT
            );

            CREATE TABLE IF NOT EXISTS team_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_slug TEXT,
                team_name TEXT,
                logo_url TEXT,
                team_type TEXT,
                dept TEXT,
                amount INTEGER,
                objectif INTEGER,
                scraped_at TEXT
            );

            CREATE TABLE IF NOT EXISTS skier_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skier_url TEXT,
                first_name TEXT,
                last_name TEXT,
                photo_url TEXT,
                team_slug TEXT,
                gender TEXT,
                amount INTEGER,
                scraped_at TEXT
            );
        """)


def insert_global(total_dons: int, total_objectif: int, scraped_at: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO global_snapshots (total_dons, total_objectif, scraped_at) VALUES (?, ?, ?)",
            (total_dons, total_objectif, scraped_at)
        )


def insert_team(team_slug: str, team_name: str, logo_url: str, team_type: str,
                dept: str, amount: int, objectif: int, scraped_at: str):
    with _conn() as con:
        con.execute(
            """INSERT INTO team_snapshots
               (team_slug, team_name, logo_url, team_type, dept, amount, objectif, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (team_slug, team_name, logo_url, team_type, dept, amount, objectif, scraped_at)
        )


def insert_skier(skier_url: str, first_name: str, last_name: str, photo_url: str,
                 team_slug: str, gender: str, amount: int, scraped_at: str):
    with _conn() as con:
        con.execute(
            """INSERT INTO skier_snapshots
               (skier_url, first_name, last_name, photo_url, team_slug, gender, amount, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (skier_url, first_name, last_name, photo_url, team_slug, gender, amount, scraped_at)
        )


def get_last_team_amount(slug: str) -> int | None:
    """Retourne le montant du dernier snapshot de l'equipe, ou None."""
    with _conn() as con:
        row = con.execute(
            "SELECT amount FROM team_snapshots WHERE team_slug = ? ORDER BY scraped_at DESC LIMIT 1",
            (slug,)
        ).fetchone()
    return row["amount"] if row else None


def get_all_latest_teams() -> list[dict]:
    """Retourne le dernier snapshot de chaque equipe."""
    with _conn() as con:
        rows = con.execute("""
            SELECT ts.*
            FROM team_snapshots ts
            INNER JOIN (
                SELECT team_slug, MAX(scraped_at) AS max_at
                FROM team_snapshots
                GROUP BY team_slug
            ) latest ON ts.team_slug = latest.team_slug AND ts.scraped_at = latest.max_at
            ORDER BY ts.amount DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_all_latest_skiers() -> list[dict]:
    """Retourne le dernier snapshot de chaque skieur."""
    with _conn() as con:
        rows = con.execute("""
            SELECT ss.*
            FROM skier_snapshots ss
            INNER JOIN (
                SELECT skier_url, MAX(scraped_at) AS max_at
                FROM skier_snapshots
                GROUP BY skier_url
            ) latest ON ss.skier_url = latest.skier_url AND ss.scraped_at = latest.max_at
            ORDER BY ss.amount DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_team_24h_delta(since_iso: str) -> list[dict]:
    """
    Retourne pour chaque equipe la difference entre le montant actuel
    et le premier montant connu depuis since_iso (24h glissantes).
    """
    with _conn() as con:
        # Montant actuel de chaque equipe
        latest = {r["team_slug"]: r["amount"] for r in con.execute("""
            SELECT ts.team_slug, ts.amount
            FROM team_snapshots ts
            INNER JOIN (
                SELECT team_slug, MAX(scraped_at) AS max_at
                FROM team_snapshots
                GROUP BY team_slug
            ) l ON ts.team_slug = l.team_slug AND ts.scraped_at = l.max_at
        """).fetchall()}

        # Premier montant connu depuis since_iso
        baseline = {r["team_slug"]: r["amount"] for r in con.execute("""
            SELECT ts.team_slug, ts.amount
            FROM team_snapshots ts
            INNER JOIN (
                SELECT team_slug, MIN(scraped_at) AS min_at
                FROM team_snapshots
                WHERE scraped_at >= ?
                GROUP BY team_slug
            ) l ON ts.team_slug = l.team_slug AND ts.scraped_at = l.min_at
        """, (since_iso,)).fetchall()}

    results = []
    for slug, current in latest.items():
        base = baseline.get(slug, current)
        results.append({"team_slug": slug, "delta_24h": current - base, "amount": current})
    results.sort(key=lambda x: x["delta_24h"], reverse=True)
    return results


def get_skiers_24h_delta(since_iso: str) -> list[dict]:
    """
    Retourne pour chaque skieur la difference de montant sur les 24h glissantes.
    """
    with _conn() as con:
        latest = {r["skier_url"]: dict(r) for r in con.execute("""
            SELECT ss.*
            FROM skier_snapshots ss
            INNER JOIN (
                SELECT skier_url, MAX(scraped_at) AS max_at
                FROM skier_snapshots
                GROUP BY skier_url
            ) l ON ss.skier_url = l.skier_url AND ss.scraped_at = l.max_at
        """).fetchall()}

        baseline = {r["skier_url"]: r["amount"] for r in con.execute("""
            SELECT ss.skier_url, ss.amount
            FROM skier_snapshots ss
            INNER JOIN (
                SELECT skier_url, MIN(scraped_at) AS min_at
                FROM skier_snapshots
                WHERE scraped_at >= ?
                GROUP BY skier_url
            ) l ON ss.skier_url = l.skier_url AND ss.scraped_at = l.min_at
        """, (since_iso,)).fetchall()}

    results = []
    for url, skier in latest.items():
        base = baseline.get(url, skier["amount"])
        entry = dict(skier)
        entry["delta_24h"] = skier["amount"] - base
        results.append(entry)
    results.sort(key=lambda x: x["delta_24h"], reverse=True)
    return results
