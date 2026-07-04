from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from schemas.responses import HTTPResponse


class APIException(HTTPException):
    def __init__(self, status: int = 400, error: str = "Bad request", data=None):
        self.status = status
        self.error = error
        self.data = data
        super().__init__(status_code=status, detail=error)

def setup_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(APIException)
    async def handle_api_exception(request: Request, exception: APIException):
        return HTTPResponse.use(
            status=exception.status,
            error=exception.error,
            data=exception.data
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exception: RequestValidationError):
        error_detail = exception.errors()[0]
        location = error_detail.get("loc", [None, None])
        parameter = location[-1] if location else None
        error_message = error_detail.get("msg", "Unknown error")
        return HTTPResponse.use(
            status=422,
            error=error_message,
            data={"loc": parameter, "param_type": location[0] if location else None}
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exception: HTTPException):
        return HTTPResponse.use(
            status=exception.status_code,
            error=exception.detail
        )

    @app.exception_handler(500)
    async def handle_internal_error(request: Request, exception: Exception):
        return HTTPResponse.use(
            status=500,
            error="Internal server error"
        )