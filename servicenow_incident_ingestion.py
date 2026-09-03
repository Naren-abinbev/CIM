from __future__ import annotations

import asyncio
import json

from backend.rag.servicenow_incident_ingestion import (
    Settings,
    ServiceNowIncidentIngestionService,
    configure_logging,
)


async def main() -> int:
    """CLI entry point for the ServiceNow incident ingestion flow."""
    configure_logging()
    settings = Settings()
    service = ServiceNowIncidentIngestionService(settings)
    summary = await service.ingest()
    print(json.dumps(summary, indent=2, default=str))
    return 1 if summary["total_fetched"] == 0 and summary["failed"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
