from collections.abc import Callable
from typing import Any


class UseCaseDispatcher:
    """Routes an immutable command/query to its registered handler."""

    def __init__(self):
        self._handlers: dict[type, Callable[[Any], Any]] = {}

    def register(self, usecase_type: type, handler: Callable[[Any], Any]) -> None:
        if usecase_type in self._handlers:
            raise ValueError(f"Handler already registered for {usecase_type.__name__}")
        self._handlers[usecase_type] = handler

    def dispatch(self, usecase: Any, **kwargs: Any) -> Any:
        handler = self._handlers.get(type(usecase))
        if handler is None:
            raise RuntimeError(f"Use case {type(usecase).__name__} is not supported")
        return handler(usecase, **kwargs)
