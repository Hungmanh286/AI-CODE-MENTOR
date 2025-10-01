from typing import Any
from fastapi import HTTPException, status


class BaseException(HTTPException):
    status_code = None
    detail = "Have exception happened."

    def __init__(self, detail: Any = None, **kwargs) -> None:
        _detail = detail or self.detail
        super().__init__(status_code=self.status_code, detail=_detail, **kwargs)


class BadRequestException(BaseException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = (
        "Request could not be processed. Please check your input or contact support."
    )


class UnauthorizedException(BaseException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authorization Required."


class NotFoundException(BaseException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "No results were found. Please retry with other input or contact support."


class ExistedException(BaseException):
    status_code = status.HTTP_409_CONFLICT
    detail = "File already existed"


class TooManyRequestsException(BaseException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded. Please wait for some time or contact the support."


class InternalServerErrorException(BaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Server process error. Please retry with other input or contact support."


class ServiceUnavailableException(BaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = (
        "Service is either overloaded or under maintenance. Please try again later."
    )
