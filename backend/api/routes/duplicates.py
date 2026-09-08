from fastapi import APIRouter, HTTPException

from backend.schemas.duplicate import (
    DuplicateIdentificationRequest,
    DuplicateIdentificationResponse
)

from backend.services.duplicate_service import (
    identify_duplicates
)


router = APIRouter(

    prefix="/duplicates",

    tags=["Duplicate Identification"]
)


@router.post(

    "/identify",

    response_model=DuplicateIdentificationResponse
)
async def identify_duplicate(

    request: DuplicateIdentificationRequest

):

    try:

        result = await identify_duplicates(request)

        return result


    except Exception as e:

        raise HTTPException(

            status_code=500,

            detail=str(e)
        )