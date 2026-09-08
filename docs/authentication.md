# Authentication

The FastAPI authentication API is independent of the incident and AI workflow.
It provides `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`,
and `GET /auth/me`. Protected APIs use `get_current_user` from
`backend.api.dependencies`.

Access JWTs expire after 15 minutes by default. Refresh JWTs expire after seven
days, are stored in SQLite only as SHA-256 hashes, and rotate on every refresh.
Reusing a revoked refresh token revokes its entire token family.

Set `JWT_SECRET_KEY` and `STREAMLIT_COOKIE_SECRET` to different high-entropy
values before deployment. Production must use HTTPS and `SECURE_COOKIES=true`.
Set `FRONTEND_ORIGIN` to the exact trusted frontend origin; wildcard CORS is not
used with credentials.

The Streamlit shell uses `streamlit-cookies-manager` to persist encrypted,
authenticated cookie values so it can restore a session after a page refresh.
Stock Streamlit cannot set `HttpOnly` cookie attributes itself. Deploy behind a
TLS-terminating reverse proxy and prefer a future BFF/proxy integration that
sets `HttpOnly; Secure; SameSite` cookies for the strongest browser boundary.
The encrypted-cookie approach is the practical compatibility trade-off and does
not place tokens in URLs, logs, or page source.

For horizontally scaled production deployments, enforce auth-route rate limits
at the gateway or substitute a shared limiter backend. The bundled limiter is a
single-process fallback and is intentionally not represented as distributed
production protection.
