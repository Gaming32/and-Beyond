from typing import Any, Optional


class AuthClientError(Exception):
    pass


class InsecureAuth(AuthClientError):
    pass


class AuthServerError(AuthClientError):
    human: Optional[str]
    info: Any
    status: int = 400

    def __init__(self, human: Optional[str], args: Any, status: Optional[int] = None) -> None:
        self.human = human
        self.info = args
        if status is not None:
            self.status = status

    def __str__(self) -> str:
        return str(self.info) if self.human is None else self.human


class ServerKeyError(AuthServerError):
    status = 400


class FormatError(AuthServerError):
    status = 400


class ServerTypeError(AuthServerError):
    status = 400


class Unauthorized(AuthServerError):
    status = 401


class ServerInsecurityError(AuthServerError):
    status = 401


class NoSuchUserError(AuthServerError):
    status = 404


class NoSuchSessionError(AuthServerError):
    status = 404


class NotFound(AuthServerError):
    status = 404


class MethodNotAllowed(AuthServerError):
    status = 405


class Conflict(AuthServerError):
    status = 409


class Ratelimited(AuthServerError):
    status = 429


class InternalServerError(AuthServerError):
    status = 500


SERVER_ERRORS: dict[str, type[AuthServerError]] = {}

for _error_type in (
    ('KeyError', ServerKeyError),
    FormatError,
    ('TypeError', ServerTypeError),
    Unauthorized,
    ('InsecurityError', ServerInsecurityError),
    NoSuchUserError,
    NoSuchSessionError,
    NotFound,
    MethodNotAllowed,
    Conflict,
    Ratelimited,
    ('InternalError', InternalServerError),
):
    if isinstance(_error_type, tuple):
        _name, _type = _error_type
    else:
        _name, _type = _error_type.__name__, _error_type
    SERVER_ERRORS[_name] = _type
