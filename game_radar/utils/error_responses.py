"""Хелпер для документирования ошибочных ответов в FastAPI-эндпоинтах."""

from __future__ import annotations

from typing import Any

from game_radar.errors import ServiceError
from game_radar.schemas.errors import ProblemDetails


def problem_from(exc: ServiceError) -> ProblemDetails:
    """Строит ProblemDetails из ServiceError — единственный источник правды
    для полей ошибки (и в реальном ответе, и в свагер-примерах)."""
    return ProblemDetails(
        type_=f"urn:game-radar:error:{exc.code}",
        status=exc.status,
        title=exc.title,
        detail=exc.detail,
        code=exc.code,
        **exc.extensions,
    )


DEFAULT_ERRORS: dict[int, ProblemDetails] = {
    401: ProblemDetails(
        type_="urn:game-radar:error:UNAUTHORIZED",
        status=401,
        title="Не авторизован",
        detail="Неверный или отсутствующий заголовок X-API-Key",
        code="UNAUTHORIZED",
    ),
    404: ProblemDetails(
        type_="urn:game-radar:error:WATCHLIST_NOT_FOUND",
        status=404,
        title="Ресурс не найден",
        detail="Запрашиваемый ресурс не найден",
        code="WATCHLIST_NOT_FOUND",
    ),
    409: ProblemDetails(
        type_="urn:game-radar:error:GAME_ALREADY_IN_WATCHLIST",
        status=409,
        title="Конфликт состояния",
        detail="Эта игра уже добавлена в список наблюдения",
        code="GAME_ALREADY_IN_WATCHLIST",
    ),
    422: ProblemDetails(
        type_="urn:game-radar:error:VALIDATION_ERROR",
        status=422,
        title="Ошибка валидации",
        detail="Ошибка валидации входных данных",
        code="VALIDATION_ERROR",
    ),
    500: ProblemDetails(
        type_="urn:game-radar:error:INTERNAL_ERROR",
        status=500,
        title="Внутренняя ошибка сервера",
        detail="An unexpected error occurred",
        code="INTERNAL_ERROR",
    ),
    503: ProblemDetails(
        type_="urn:game-radar:error:PRICE_PROVIDER_UNAVAILABLE",
        status=503,
        title="Внешний сервис недоступен",
        detail="Сервис цен CheapShark временно недоступен, попробуйте позже",
        code="PRICE_PROVIDER_UNAVAILABLE",
    ),
}


def get_error_responses(
    *codes_or_instances: int | ProblemDetails,
) -> dict[int | str, dict[str, Any]]:
    """
    Генерирует responses для FastAPI. Принимает коды (из DEFAULT_ERRORS)
    или готовые экземпляры ProblemDetails для кастомных примеров.
    Несколько инстансов с одинаковым status объединяются в один response
    с несколькими именованными examples (по code), а не затирают друг друга.
    """
    instances_by_status: dict[int, list[ProblemDetails]] = {}
    for item in codes_or_instances:
        if isinstance(item, int):
            instance = DEFAULT_ERRORS.get(item)
            if not instance:
                continue
        else:
            instance = item
        instances_by_status.setdefault(instance.status, []).append(instance)

    responses: dict[int | str, dict[str, Any]] = {}
    for status, instances in instances_by_status.items():
        examples = {
            instance.code: {"value": instance.model_dump(by_alias=True)} for instance in instances
        }
        responses[status] = {
            "model": type(instances[0]),
            "description": instances[0].title,
            "content": {"application/json": {"examples": examples}},
        }
    return responses
