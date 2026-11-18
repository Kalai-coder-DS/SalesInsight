"""Phase 1 tests: configuration and logging."""

from __future__ import annotations

import logging

from salesinsight import config
from salesinsight.logger import get_logger


def test_project_root_is_correct():
    # The project root must contain pyproject.toml and the src folder.
    assert (config.PROJECT_ROOT / "pyproject.toml").exists()
    assert (config.PROJECT_ROOT / "src" / "salesinsight").is_dir()


def test_paths_are_inside_project():
    for folder in config.ALL_DIRS:
        assert config.PROJECT_ROOT in folder.parents


def test_ensure_directories_creates_all_folders():
    config.ensure_directories()
    for folder in config.ALL_DIRS:
        assert folder.is_dir(), f"Missing folder: {folder}"


def test_data_file_names():
    assert config.RAW_DATA_FILE.name == "Superstore.csv"
    assert config.CLEAN_DATA_FILE.name == "sales_clean.csv"


def test_logger_writes_to_file():
    logger = get_logger("test_logger_file")
    logger.info("phase-1-test-message")
    for handler in logger.handlers:
        handler.flush()
    assert config.LOG_FILE.exists()
    assert "phase-1-test-message" in config.LOG_FILE.read_text(encoding="utf-8")


def test_logger_has_no_duplicate_handlers():
    first = get_logger("test_logger_dupes")
    second = get_logger("test_logger_dupes")
    assert first is second
    assert len(second.handlers) == 2  # one console + one file
    assert any(isinstance(h, logging.FileHandler) for h in second.handlers)


def test_mysql_url_handles_special_characters(monkeypatch):
    monkeypatch.setattr(config, "MYSQL_PASSWORD", "p@ss#word")
    url = config.get_mysql_url()
    assert url.password == "p@ss#word"
    assert url.drivername == "mysql+pymysql"
    assert url.database == config.MYSQL_DATABASE
    # The password must never appear when the URL is printed or logged.
    assert "p@ss#word" not in str(url)


def test_mysql_url_without_database():
    url = config.get_mysql_url(include_database=False)
    assert url.database is None
