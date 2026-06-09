from __future__ import annotations

import sys

from loguru import logger


def setup_logging(env: str, level: str = "INFO") -> None:
    logger.remove()

    serialize = env == "production"

    logger.add(
        sys.stdout,
        level=level.upper(),
        enqueue=True,
        backtrace=env != "production",
        diagnose=env != "production",
        serialize=serialize,
    )