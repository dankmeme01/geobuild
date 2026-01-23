from typing import NoReturn

class GeobuildError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)

def fatal_error(message: str) -> NoReturn:
    raise GeobuildError(message)