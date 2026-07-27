"""Structured logging setup for the club price tracker.

get_logger() always logs to the console; pass write_to_file=True to
also write the same lines to a timestamped file under logs/ (gitignored),
so a run's output can be reviewed later without rerunning it.
"""

import logging
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"


def get_logger(name: str, write_to_file: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if write_to_file:
        LOG_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_handler = logging.FileHandler(LOG_DIR / f"run_{timestamp}.txt")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
