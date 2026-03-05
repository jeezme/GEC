import logging

from db import init_db
from gender import warn_unknown_genders
from scraper import scrape_all
from report import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def main():
    log.info("=== Demarrage du scraping ===")
    init_db()
    warn_unknown_genders()
    scrape_all()
    log.info("=== Generation du rapport ===")
    path = generate_report()
    log.info("=== Termine : %s ===", path)


if __name__ == "__main__":
    main()
