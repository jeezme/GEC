import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_DIR = "/data"
DB_PATH = os.path.join(DB_DIR, "glisse.db")


def _conn():
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
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
                team_slug TEXT, team_name TEXT, logo_url TEXT,
                team_type TEXT, dept TEXT, amount INTEGER,
                objectif INTEGER, scraped_at TEXT, logo_base64 TEXT
            );
            CREATE TABLE IF NOT EXISTS skier_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skier_url TEXT, first_name TEXT, last_name TEXT,
                photo_url TEXT, team_slug TEXT, gender TEXT,
                amount INTEGER, scraped_at TEXT, photo_base64 TEXT
            );
        """)



def _migrate_db():
    """Ajoute les colonnes base64 si absentes (migration schema)."""
    with _conn() as con:
        for sql in [
            "ALTER TABLE team_snapshots ADD COLUMN logo_base64 TEXT",
            "ALTER TABLE skier_snapshots ADD COLUMN photo_base64 TEXT",
        ]:
            try:
                con.execute(sql)
            except Exception:
                pass  # colonne deja existante

def insert_global(total_dons: int, total_objectif: int, scraped_at: str):
    with _conn() as con:
        con.execute(
            "INSERT INTO global_snapshots (total_dons, total_objectif, scraped_at) VALUES (?, ?, ?)",
            (total_dons, total_objectif, scraped_at)
        )


def insert_team(team_slug, team_name, logo_url, logo_base64, team_type, dept, amount, objectif, scraped_at):
    with _conn() as con:
        con.execute(
            "INSERT INTO team_snapshots "
            "(team_slug, team_name, logo_url, logo_base64, team_type, dept, amount, objectif, scraped_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (team_slug, team_name, logo_url, logo_base64, team_type, dept, amount, objectif, scraped_at)
        )


def insert_skier(skier_url, first_name, last_name, photo_url, photo_base64, team_slug, gender, amount, scraped_at):
    with _conn() as con:
        con.execute(
            "INSERT INTO skier_snapshots "
            "(skier_url, first_name, last_name, photo_url, photo_base64, team_slug, gender, amount, scraped_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (skier_url, first_name, last_name, photo_url, photo_base64, team_slug, gender, amount, scraped_at)
        )


def get_last_team_amount(slug: str) -> int | None:
    with _conn() as con:
        row = con.execute(
            "SELECT amount FROM team_snapshots WHERE team_slug = ? ORDER BY scraped_at DESC LIMIT 1",
            (slug,)
        ).fetchone()
    return row["amount"] if row else None


def get_all_latest_teams() -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT ts.id, ts.team_slug, ts.team_name, ts.logo_url, ts.logo_base64, ts.team_type,
                   ts.dept, ts.amount, ts.objectif, ts.scraped_at
            FROM team_snapshots ts
            INNER JOIN (
                SELECT team_slug, MAX(scraped_at) AS max_at
                FROM team_snapshots GROUP BY team_slug
            ) latest ON ts.team_slug = latest.team_slug AND ts.scraped_at = latest.max_at
            ORDER BY ts.amount DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_all_latest_skiers() -> list[dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT ss.id, ss.skier_url, ss.first_name, ss.last_name, ss.photo_url,
                   ss.team_slug, ss.gender, ss.amount, ss.scraped_at
            FROM skier_snapshots ss
            INNER JOIN (
                SELECT skier_url, MAX(scraped_at) AS max_at
                FROM skier_snapshots GROUP BY skier_url
            ) latest ON ss.skier_url = latest.skier_url AND ss.scraped_at = latest.max_at
            ORDER BY ss.amount DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_team_24h_delta() -> list[dict]:
    """Delta entre snapshot actuel et snapshot le plus proche de now()-24h (fenetre 23h-25h)."""
    now = datetime.now(timezone.utc)
    target = now - timedelta(hours=24)
    win_start = (now - timedelta(hours=25)).isoformat()
    win_end = (now - timedelta(hours=23)).isoformat()
    target_iso = target.isoformat()

    with _conn() as con:
        latest = {r["team_slug"]: r["amount"] for r in con.execute("""
            SELECT ts.team_slug, ts.amount FROM team_snapshots ts
            INNER JOIN (
                SELECT team_slug, MAX(scraped_at) AS max_at
                FROM team_snapshots GROUP BY team_slug
            ) l ON ts.team_slug = l.team_slug AND ts.scraped_at = l.max_at
        """).fetchall()}

        baseline_rows = con.execute(
            "SELECT team_slug, amount, "
            "ABS(JULIANDAY(scraped_at) - JULIANDAY(?)) AS diff "
            "FROM team_snapshots WHERE scraped_at BETWEEN ? AND ?",
            (target_iso, win_start, win_end)
        ).fetchall()

        first_rows = con.execute("""
            SELECT ts.team_slug, ts.amount FROM team_snapshots ts
            INNER JOIN (
                SELECT team_slug, MIN(scraped_at) AS min_at
                FROM team_snapshots GROUP BY team_slug
            ) l ON ts.team_slug = l.team_slug AND ts.scraped_at = l.min_at
        """).fetchall()

    first_snap = {r["team_slug"]: r["amount"] for r in first_rows}

    baseline = {}
    for r in baseline_rows:
        slug = r["team_slug"]
        if slug not in baseline or r["diff"] < baseline[slug]["diff"]:
            baseline[slug] = {"amount": r["amount"], "diff": r["diff"]}

    results = []
    for slug, current in latest.items():
        base = baseline[slug]["amount"] if slug in baseline else first_snap.get(slug, current)
        results.append({"team_slug": slug, "delta_24h": current - base, "amount": current})
    results.sort(key=lambda x: x["delta_24h"], reverse=True)
    return results


def get_skiers_24h_delta() -> list[dict]:
    """Delta entre snapshot actuel et snapshot le plus proche de now()-24h (fenetre 23h-25h)."""
    now = datetime.now(timezone.utc)
    target = now - timedelta(hours=24)
    win_start = (now - timedelta(hours=25)).isoformat()
    win_end = (now - timedelta(hours=23)).isoformat()
    target_iso = target.isoformat()

    with _conn() as con:
        latest = {r["skier_url"]: dict(r) for r in con.execute("""
            SELECT ss.id, ss.skier_url, ss.first_name, ss.last_name, ss.photo_url,
                   ss.team_slug, ss.gender, ss.amount, ss.scraped_at
            FROM skier_snapshots ss
            INNER JOIN (
                SELECT skier_url, MAX(scraped_at) AS max_at
                FROM skier_snapshots GROUP BY skier_url
            ) l ON ss.skier_url = l.skier_url AND ss.scraped_at = l.max_at
        """).fetchall()}

        baseline_rows = con.execute(
            "SELECT skier_url, amount, "
            "ABS(JULIANDAY(scraped_at) - JULIANDAY(?)) AS diff "
            "FROM skier_snapshots WHERE scraped_at BETWEEN ? AND ?",
            (target_iso, win_start, win_end)
        ).fetchall()

        first_rows = con.execute("""
            SELECT ss.skier_url, ss.amount FROM skier_snapshots ss
            INNER JOIN (
                SELECT skier_url, MIN(scraped_at) AS min_at
                FROM skier_snapshots GROUP BY skier_url
            ) l ON ss.skier_url = l.skier_url AND ss.scraped_at = l.min_at
        """).fetchall()

    first_snap = {r["skier_url"]: r["amount"] for r in first_rows}

    baseline = {}
    for r in baseline_rows:
        url = r["skier_url"]
        if url not in baseline or r["diff"] < baseline[url]["diff"]:
            baseline[url] = {"amount": r["amount"], "diff": r["diff"]}

    results = []
    for url, skier in latest.items():
        base = baseline[url]["amount"] if url in baseline else first_snap.get(url, skier["amount"])
        entry = dict(skier)
        entry["delta_24h"] = skier["amount"] - base
        results.append(entry)
    results.sort(key=lambda x: x["delta_24h"], reverse=True)
    return results


def purge_old_snapshots(hours: int = 36) -> dict:
    """Supprime les snapshots plus vieux que `hours` heures et libère l'espace disque (VACUUM)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as con:
        g = con.execute("DELETE FROM global_snapshots WHERE scraped_at < ?", (cutoff,)).rowcount
        t = con.execute("DELETE FROM team_snapshots WHERE scraped_at < ?", (cutoff,)).rowcount
        s = con.execute("DELETE FROM skier_snapshots WHERE scraped_at < ?", (cutoff,)).rowcount
    # VACUUM doit être hors transaction
    con2 = _conn()
    try:
        con2.execute("VACUUM")
    finally:
        con2.close()
    return {"global": g, "teams": t, "skiers": s}


def get_recent_dons(limit: int = 20) -> list[dict]:
    """Detecte les dons via LAG sur snapshots consecutifs. Fusionne equipes + skieurs."""
    with _conn() as con:
        team_dons = con.execute(
            "SELECT 'team' AS source, team_name AS display_name, "
            "'' AS team_slug, scraped_at, don_amount FROM ("
            "SELECT team_name, scraped_at, "
            "amount - LAG(amount,1,amount) OVER (PARTITION BY team_slug ORDER BY scraped_at) AS don_amount "
            "FROM team_snapshots) WHERE don_amount > 0 ORDER BY scraped_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

        skier_dons = con.execute(
            "SELECT 'skier' AS source, "
            "(first_name || ' ' || UPPER(last_name)) AS display_name, "
            "team_slug, scraped_at, don_amount FROM ("
            "SELECT first_name, last_name, team_slug, scraped_at, "
            "amount - LAG(amount,1,amount) OVER (PARTITION BY skier_url ORDER BY scraped_at) AS don_amount "
            "FROM skier_snapshots) WHERE don_amount > 0 ORDER BY scraped_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

        team_names = {}
        if skier_dons:
            team_names = {
                r["team_slug"]: r["team_name"]
                for r in con.execute(
                    "SELECT team_slug, team_name FROM team_snapshots GROUP BY team_slug"
                ).fetchall()
            }

    combined = [dict(r) for r in team_dons]
    for r in skier_dons:
        d = dict(r)
        d["team_name"] = team_names.get(d.get("team_slug") or "", "")
        combined.append(d)
    combined.sort(key=lambda x: x["scraped_at"], reverse=True)
    return combined[:limit]
