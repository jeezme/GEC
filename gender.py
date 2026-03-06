import json
import os
import logging

import gender_guesser.detector as gender_lib

OVERRIDES_FILE = "genders_overrides.json"
_detector = gender_lib.Detector(case_sensitive=False)
log = logging.getLogger(__name__)


def detect_gender(first_name: str) -> str:
    """Retourne 'M' ou 'F'. Consulte d'abord les overrides manuels."""
    name = first_name.strip().capitalize()

    overrides = _load_overrides()
    if name in overrides:
        val = overrides[name]
        if val in ("M", "F"):
            return val

    result = _detector.get_gender(name)
    if result in ("male", "mostly_male"):
        return "M"
    if result in ("female", "mostly_female"):
        return "F"

    if name not in overrides or overrides.get(name) not in ("M", "F"):
        overrides[name] = "?"
        _save_overrides(overrides)

    return "M"


def warn_unknown_genders():
    """Affiche dans les logs les prenoms avec genre inconnu."""
    overrides = _load_overrides()
    unknowns = [k for k, v in overrides.items() if v == "?"]
    if unknowns:
        names = ", ".join(unknowns)
        log.warning(
            "⚠️  %d prenom(s) a genre inconnu dans genders_overrides.json : %s",
            len(unknowns), names
        )
        log.warning("   → Editez ce fichier et remplacez \"?\" par \"M\" ou \"F\"")


def _load_overrides() -> dict:
    if os.path.exists(OVERRIDES_FILE):
        with open(OVERRIDES_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_overrides(new_entries: dict):
    existing = _load_overrides()
    changed = False
    for name, value in new_entries.items():
        if name not in existing:
            existing[name] = value
            changed = True
    if changed:
        with open(OVERRIDES_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2, sort_keys=True)
