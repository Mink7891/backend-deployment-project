"""UseCase-датаклассы служебных проверок."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetHealthUseCase:
    """GET /health — БД доступна и схема установлена."""

    pass
