import logging
from app.core.config import settings

def setup_logging():
    level_name = settings.LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Reduce noise from arq and sqlalchemy if not explicitly requested
    if level > logging.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("arq").setLevel(logging.INFO)

setup_logging()
logger = logging.getLogger("comp_intel")
