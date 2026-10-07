"""UseCase-диспетчер — маршрутизирует UseCase-типы к обработчикам."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

HandlerFn = Callable[..., Awaitable[object]]


class UseCaseDispatcher:
    """Центральный диспетчер, маршрутизирующий UseCase-датаклассы к их обработчикам."""

    def __init__(self) -> None:
        self._handlers: dict[type[object], HandlerFn] = {}

    def register(self, usecase_type: type[object], handler_fn: HandlerFn) -> None:
        """Регистрирует функцию-обработчик для заданного типа UseCase."""
        self._handlers[usecase_type] = handler_fn

    async def dispatch(self, usecase: object, session: AsyncSession) -> object:
        """Передаёт UseCase зарегистрированному обработчику."""
        usecase_type = type(usecase)
        handler_fn = self._handlers.get(usecase_type)
        if handler_fn is None:
            raise ValueError(f"No handler registered for UseCase: {usecase_type.__name__}")
        return await handler_fn(usecase, session)
