"""CASE API error response helpers and exception classes."""

from fastapi.responses import JSONResponse

from src.schemas.common import ImsxCodeMinor, ImsxCodeMinorField, ImsxStatusInfo


def imsx_error_response(
    status_code: int,
    description: str,
    code_minor_value: str,
    field_name: str = "sourcedId",
) -> JSONResponse:
    """Build an imsx_StatusInfo error response.

    ``field_name`` sets ``imsx_codeMinorFieldName``. It defaults to the imsx
    convention ``"sourcedId"``; pass the offending parameter name (e.g. ``sort``
    / ``fields`` / ``limit``) when it is more meaningful to the client.
    """
    body = ImsxStatusInfo(
        imsx_codeMajor="failure",
        imsx_severity="error",
        imsx_description=description,
        imsx_codeMinor=ImsxCodeMinor(
            imsx_codeMinorField=[
                ImsxCodeMinorField(
                    imsx_codeMinorFieldName=field_name,
                    imsx_codeMinorFieldValue=code_minor_value,
                )
            ]
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(by_alias=True),
    )


class InvalidUUIDError(Exception):
    def __init__(self, message: str):
        self.message = message


class ResourceNotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message
