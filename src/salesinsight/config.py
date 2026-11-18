"""Central configuration: folder paths, file names and database settings.

Every other module imports paths and settings from here, so nothing is
hard-coded in more than one place.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Folder paths
# ---------------------------------------------------------------------------
# This file lives at  <project>/src/salesinsight/config.py
# parents[0] = salesinsight, parents[1] = src, parents[2] = project root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
SAMPLE_DATA_DIR: Path = DATA_DIR / "sample"

SQL_DIR: Path = PROJECT_ROOT / "sql"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
FIGURES_DIR: Path = REPORTS_DIR / "figures"
TABLES_DIR: Path = REPORTS_DIR / "tables"
LOGS_DIR: Path = PROJECT_ROOT / "logs"

# ---------------------------------------------------------------------------
# File names
# ---------------------------------------------------------------------------
RAW_DATA_FILE: Path = RAW_DATA_DIR / "Superstore.csv"
CLEAN_DATA_FILE: Path = PROCESSED_DATA_DIR / "sales_clean.csv"
LOG_FILE: Path = LOGS_DIR / "salesinsight.log"

# The Kaggle Superstore CSV is not UTF-8; latin-1 reads every byte safely.
RAW_DATA_ENCODING: str = "latin-1"

# Fixed seed so any random step gives the same result every run.
RANDOM_SEED: int = 42

# ---------------------------------------------------------------------------
# Settings from the .env file
# ---------------------------------------------------------------------------
load_dotenv(PROJECT_ROOT / ".env")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "salesinsight")

ALL_DIRS: tuple[Path, ...] = (
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    SAMPLE_DATA_DIR,
    SQL_DIR,
    FIGURES_DIR,
    TABLES_DIR,
    LOGS_DIR,
)


def ensure_directories() -> None:
    """Create every project folder if it does not exist yet."""
    for folder in ALL_DIRS:
        folder.mkdir(parents=True, exist_ok=True)


def get_mysql_url(include_database: bool = True):
    """Build a SQLAlchemy connection URL for MySQL.

    URL.create() is used instead of an f-string so that passwords
    containing special characters such as @ or # still work.

    Args:
        include_database: False connects to the server only, which is
            needed before the database itself has been created.
    """
    from sqlalchemy import URL  # imported here so config works without SQLAlchemy

    return URL.create(
        drivername="mysql+pymysql",
        username=MYSQL_USER,
        password=MYSQL_PASSWORD,
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=MYSQL_DATABASE if include_database else None,
    )
