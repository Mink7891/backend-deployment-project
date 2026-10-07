"""Каталог ошибок сервиса Game Radar (RFC 9457 Problem Details)."""

from __future__ import annotations


class ServiceError(Exception):
    """Базовая сервисная ошибка с деталями по RFC 9457."""

    def __init__(
        self,
        code: str,
        status: int,
        title: str,
        detail: str,
        **extensions: str,
    ) -> None:
        self.code = code
        self.status = status
        self.title = title
        self.detail = detail
        self.extensions = extensions
        super().__init__(detail)


# --- Фабричные функции ошибок ---


def unauthorized() -> ServiceError:
    return ServiceError(
        code="UNAUTHORIZED",
        status=401,
        title="Не авторизован",
        detail="Неверный или отсутствующий заголовок X-API-Key",
    )


def game_not_found() -> ServiceError:
    return ServiceError(
        code="GAME_NOT_FOUND",
        status=404,
        title="Игра не найдена",
        detail="Игра с таким идентификатором не найдена у провайдера цен",
    )


def game_not_in_catalog() -> ServiceError:
    return ServiceError(
        code="GAME_NOT_IN_CATALOG",
        status=404,
        title="Игры нет в каталоге",
        detail="Игры нет в локальном каталоге; сначала запросите её цены",
    )


def watchlist_not_found() -> ServiceError:
    return ServiceError(
        code="WATCHLIST_NOT_FOUND",
        status=404,
        title="Список не найден",
        detail="Список наблюдения не найден",
    )


def watchlist_item_not_found() -> ServiceError:
    return ServiceError(
        code="WATCHLIST_ITEM_NOT_FOUND",
        status=404,
        title="Игра в списке не найдена",
        detail="Позиция списка наблюдения не найдена",
    )


def game_already_in_watchlist() -> ServiceError:
    return ServiceError(
        code="GAME_ALREADY_IN_WATCHLIST",
        status=409,
        title="Игра уже в списке",
        detail="Эта игра уже добавлена в список наблюдения",
    )


def price_provider_unavailable() -> ServiceError:
    return ServiceError(
        code="PRICE_PROVIDER_UNAVAILABLE",
        status=503,
        title="Провайдер цен недоступен",
        detail="Сервис цен CheapShark временно недоступен, попробуйте позже",
    )
