from backend.schemas.duplicate import (
    DuplicateIdentificationRequest
)

from backend.rag.duplicate_pipeline import (
    run_duplicate_identification
)


async def identify_duplicates(
    request: DuplicateIdentificationRequest
):

    # ==========================================
    # CALL DUPLICATE IDENTIFICATION PIPELINE
    # ==========================================

    pipeline_result = await run_duplicate_identification(

        title=request.title,

        description=request.description,

        severity=request.severity,

        service=request.serviceId,

        zone=request.zone
    )


    # ==========================================
    # CONVERT PIPELINE RESPONSE
    # TO UI RESPONSE FORMAT
    # ==========================================

    duplicates = []


    for item in pipeline_result.get(
        "matches",
        []
    ):

        duplicates.append({

            "id": item.get(
                "id",
                item.get("incident_id")
            ),

            "subject": item.get(
                "subject",
                item.get("title")
            ),

            "severity": item.get(
                "severity",
                "UNKNOWN"
            ),

            "status": item.get(
                "status",
                "UNKNOWN"
            ),

            "serviceId": item.get(
                "serviceId",
                item.get("service")
            ),

            "zone": item.get(
                "zone",
                "UNKNOWN"
            ),

            "matchPercentage": int(

                item.get(
                    "matchPercentage",

                    item.get(
                        "similarity_score",
                        0
                    ) * 100
                )

            ),

            "createdAt": item.get(
                "createdAt",
                item.get("created_at")
            ),

            "resolvedAt": item.get(
                "resolvedAt",
                item.get("resolved_at")
            )
        })


    return {

        "data": duplicates
    }