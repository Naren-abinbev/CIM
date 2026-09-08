from __future__ import annotations

import os
import sys
from pathlib import Path

# Add the CIM project root to Python's import path.
# This allows imports such as:
# from backend.ai.agents.intent_agent import analyze_intent
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


# Keep authentication tests independent from a developer's local .env file.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-and-not-production")
os.environ.setdefault("BCRYPT_ROUNDS", "4")

