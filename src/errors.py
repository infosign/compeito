"""CASE API error response helpers and exception classes."""

from fastapi.responses import JSONResponse

from src.schemas.common import ImsxCodeMinor, ImsxCodeMinorField, ImsxStatusInfo


def imsx_error_response(
    status_code: int,
    description: str,
    code_minor_value: str,
) -> JSONResponse:
    body = ImsxStatusInfo(
        imsx_codeMajor="failure",
        imsx_severity="error",
        imsx_description=description,
        imsx_codeMinor=ImsxCodeMinor(
            imsx_codeMinorField=[ImsxCodeMinorField(imsx_codeMinorFieldValue=code_minor_value)]
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
