import time

_cache = {}
_scraping = False
_scraping_status = {}


def get(key):
    return _cache.get(key)


def set(key, data):
    _cache[key] = data


def flush():
    _cache.clear()


def set_scraping(value: bool, status: dict = {}):
    global _scraping, _scraping_status
    _scraping = value
    _scraping_status = status


def get_status():
    return {"scraping": _scraping, **_scraping_status}
