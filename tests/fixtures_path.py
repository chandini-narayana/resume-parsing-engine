"""Shared helper: absolute path to the checked-in test fixtures directory."""

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
