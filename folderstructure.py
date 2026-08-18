from pathlib import Path


# CIM is already the project root
PROJECT_ROOT = Path(".")


DIRECTORIES = [
    # Frontend
    "frontend/components",
    "frontend/pages",
    "frontend/services",

    # Backend
    "backend/api/routes",
    "backend/services",

    # AI
    "backend/ai/orchestrator",
    "backend/ai/agents",
    "backend/ai/tools",
    "backend/ai/workflow",
    "backend/ai/memory",
    "backend/ai/evaluation",
    "backend/ai/prompts",

    # RAG
    "backend/rag",

    # Database
    "backend/database",

    # Backend infrastructure
    "backend/middleware",
    "backend/auth",
    "backend/logging",
    "backend/schemas",

    # Integrations
    "integrations/servicenow",
    "integrations/teams",
    "integrations/cmdb",
    "integrations/notifications",
    "integrations/azure",

    # Local data
    "data/sqlite",
    "data/chroma",

    # Tests
    "tests/unit/agents",
    "tests/unit/services",
    "tests/unit/rag",
    "tests/unit/workflow",
    "tests/integration/servicenow",
    "tests/integration/teams",
    "tests/integration/rag",
    "tests/e2e/incident_workflow",

    # Documentation
    "docs",

    # Sample data
    "sample_data/incidents",
    "sample_data/transcripts",
    "sample_data/resolutions",

    # Scripts
    "scripts",
]


FILES = [
    # Root
    "README.md",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    ".env",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "docker-compose.yml",
    "project_context.md",

    # Frontend
    "frontend/app.py",
    "frontend/components/incident_form.py",
    "frontend/components/incident_status.py",
    "frontend/components/common.py",
    "frontend/pages/submit_incident.py",
    "frontend/pages/incident_status.py",
    "frontend/pages/admin.py",
    "frontend/services/api_client.py",

    # Backend
    "backend/main.py",

    # API
    "backend/api/router.py",
    "backend/api/dependencies.py",
    "backend/api/routes/incidents.py",
    "backend/api/routes/warroom.py",
    "backend/api/routes/transcripts.py",
    "backend/api/routes/health.py",

    # Services
    "backend/services/incident_service.py",
    "backend/services/duplicate_service.py",
    "backend/services/severity_service.py",
    "backend/services/warroom_service.py",
    "backend/services/transcript_service.py",
    "backend/services/resolution_service.py",
    "backend/services/knowledge_service.py",

    # AI - Orchestrator
    "backend/ai/orchestrator/agent_orchestrator.py",

    # AI - Agents
    "backend/ai/agents/duplicate_agent.py",
    "backend/ai/agents/severity_agent.py",
    "backend/ai/agents/investigation_agent.py",
    "backend/ai/agents/resolution_agent.py",
    "backend/ai/agents/transcript_agent.py",
    "backend/ai/agents/validation_agent.py",

    # AI - Tools
    "backend/ai/tools/rag_tools.py",
    "backend/ai/tools/teams_tools.py",
    "backend/ai/tools/servicenow_tools.py",

    # AI - LangGraph
    "backend/ai/workflow/graph.py",
    "backend/ai/workflow/state.py",
    "backend/ai/workflow/nodes.py",

    # AI - Memory
    "backend/ai/memory/working_memory.py",
    "backend/ai/memory/episodic_memory.py",
    "backend/ai/memory/memory_manager.py",

    # AI - Evaluation
    "backend/ai/evaluation/evaluator.py",
    "backend/ai/evaluation/metrics.py",

    # AI - Prompts
    "backend/ai/prompts/duplicate.py",
    "backend/ai/prompts/investigation.py",
    "backend/ai/prompts/transcript.py",
    "backend/ai/prompts/resolution.py",
    "backend/ai/prompts/validation.py",

    # RAG
    "backend/rag/chroma.py",
    "backend/rag/embeddings.py",
    "backend/rag/retriever.py",
    "backend/rag/reranker.py",
    "backend/rag/ingestion.py",

    # Database
    "backend/database/database.py",
    "backend/database/models.py",
    "backend/database/repositories.py",

    # Middleware
    "backend/middleware/error_handler.py",
    "backend/middleware/correlation_id.py",
    "backend/middleware/request_logging.py",

    # Auth
    "backend/auth/authentication.py",

    # Logging
    "backend/logging/logger.py",
    "backend/logging/agent_logger.py",
    "backend/logging/audit_logger.py",

    # Schemas
    "backend/schemas/incident.py",
    "backend/schemas/warroom.py",
    "backend/schemas/transcript.py",
    "backend/schemas/resolution.py",

    # ServiceNow
    "integrations/servicenow/client.py",
    "integrations/servicenow/incident.py",

    # Teams
    "integrations/teams/client.py",
    "integrations/teams/warroom.py",
    "integrations/teams/transcript.py",

    # CMDB
    "integrations/cmdb/client.py",

    # Notifications
    "integrations/notifications/email.py",
    "integrations/notifications/teams.py",

    # Azure
    "integrations/azure/client.py",

    # Integration documentation
    "integrations/README.md",

    # Documentation
    "docs/architecture.md",
    "docs/workflow.md",
    "docs/agents.md",
    "docs/rag.md",
    "docs/integrations.md",
    "docs/setup.md",

    # Scripts
    "scripts/seed_data.py",
    "scripts/initialize_db.py",
    "scripts/initialize_chroma.py",
]


def create_project_structure():
    print(f"\nProject root: {Path.cwd()}\n")

    # Create directories
    for directory in DIRECTORIES:
        path = PROJECT_ROOT / directory
        path.mkdir(parents=True, exist_ok=True)

    # Create files
    for file in FILES:
        path = PROJECT_ROOT / file
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            path.touch()

    print("CIM project structure created successfully.")


if __name__ == "__main__":
    create_project_structure()