from fastapi import Request
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    status_code = 500
    code = "application_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class BadRequestError(ApplicationError):
    status_code = 400
    code = "bad_request"


class NotFoundError(ApplicationError):
    status_code = 404
    code = "not_found"


async def application_error_handler(
    _request: Request, exc: ApplicationError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "SoulSmith failed to process the request.",
            }
        },
    )
