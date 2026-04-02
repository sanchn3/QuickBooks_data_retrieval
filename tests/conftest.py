"""
conftest.py — Shared pytest setup.

Loads .env from the project root so Supabase integration tests can use real
credentials when available.  Falls back to placeholder values so all unit
tests run without any .env file present.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path so test files can import project modules
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env if present (provides real Supabase creds for integration tests)
from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

# Fallback placeholders — keeps config.py importable without a real .env
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "placeholder-key")
