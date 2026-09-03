from __future__ import annotations

import os


# Keep authentication tests independent from a developer's local .env file.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-and-not-production")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
