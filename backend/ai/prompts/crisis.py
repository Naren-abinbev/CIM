CRISIS_ANALYSIS_PROMPT = """
Analyze the crisis incident report below.

Return exactly:
1. A brief summary of the key issue.
2. The top {top_k} relevant internal documents, policies, or procedures to reference.
3. The top {top_k} immediate, high-priority actions.

Clearly separate the three sections. Base recommendations only on the report.
Do not invent document titles, policies, facts, owners, or completed actions.
When a specific reference cannot be identified, describe the type of internal
document or policy that should be located and say that it needs verification.
Prioritize safety, containment, escalation, and evidence preservation where
the report supports them.

Crisis type: {crisis_type}

Crisis incident report:
{report}
""".strip()