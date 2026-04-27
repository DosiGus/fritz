"""Test fixtures: ensure imports don't require a real database or telegram token."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("USDA_API_KEY", "")
