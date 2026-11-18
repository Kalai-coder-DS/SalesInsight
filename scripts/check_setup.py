"""Phase 1 health check.

Run from the project root:
    python scripts/check_setup.py

It checks: Python version, required packages, project folders,
the .env file, and the connection to your MySQL server.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import sys

from salesinsight import config
from salesinsight.logger import get_logger

logger = get_logger("check_setup")

# import name -> name shown in the report
REQUIRED_PACKAGES = {
    "pandas": "pandas",
    "numpy": "numpy",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    "sqlalchemy": "SQLAlchemy",
    "pymysql": "PyMySQL",
    "cryptography": "cryptography",
    "dotenv": "python-dotenv",
    "pytest": "pytest",
}


def check_python() -> bool:
    version = sys.version_info
    ok = version >= (3, 10)
    status = "OK" if ok else "TOO OLD (need 3.10+)"
    logger.info("Python %d.%d.%d ... %s", version.major, version.minor, version.micro, status)
    return ok


def check_packages() -> bool:
    all_ok = True
    for import_name, display_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
            version = importlib.metadata.version(display_name)
            logger.info("%-14s %s ... OK", display_name, version)
        except ImportError:
            logger.error("%-14s ... MISSING  (run: pip install -r requirements.txt)", display_name)
            all_ok = False
    return all_ok


def check_folders() -> bool:
    config.ensure_directories()
    for folder in config.ALL_DIRS:
        logger.info("Folder %-32s ... OK", folder.relative_to(config.PROJECT_ROOT).as_posix())
    return True


def check_env_file() -> bool:
    env_path = config.PROJECT_ROOT / ".env"
    if not env_path.exists():
        logger.error(".env file not found. Copy .env.example to .env and add your password.")
        return False
    if config.MYSQL_PASSWORD in ("", "your_mysql_password_here"):
        logger.error(".env found, but MYSQL_PASSWORD is still empty or the placeholder.")
        return False
    logger.info(".env file ... OK (user=%s, host=%s:%s)", config.MYSQL_USER, config.MYSQL_HOST, config.MYSQL_PORT)
    return True


def check_mysql() -> bool:
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        logger.error("SQLAlchemy is not installed, cannot test MySQL.")
        return False

    engine = create_engine(config.get_mysql_url(include_database=False))
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
        logger.info("MySQL server %s ... connected OK", version)
        return True
    except Exception as exc:  # show a short, readable reason
        logger.error("MySQL connection FAILED: %s", str(exc).splitlines()[0])
        logger.error("Check that the MySQL service is running and the .env values are correct.")
        return False
    finally:
        engine.dispose()


def main() -> int:
    logger.info("=" * 60)
    logger.info("SalesInsight - Phase 1 setup check")
    logger.info("=" * 60)

    results = {
        "Python version": check_python(),
        "Packages": check_packages(),
        "Folders": check_folders(),
        ".env file": check_env_file(),
    }
    results["MySQL connection"] = check_mysql() if results[".env file"] else False

    logger.info("-" * 60)
    for name, ok in results.items():
        logger.info("%-18s %s", name, "PASS" if ok else "FAIL")
    logger.info("-" * 60)

    if all(results.values()):
        logger.info("All checks passed. Phase 1 is complete.")
        return 0
    logger.error("Some checks failed. Fix the items marked FAIL and run again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
