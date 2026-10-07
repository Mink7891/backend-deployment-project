"""Worker-only DTOs, outside the public HTTP/OpenAPI contract."""

from app.schemas.base import DTO


class RefreshBatchResponse(DTO):
    refreshed_games: int
    checked_items: int
    matched_count: int
    notifications_created: int
    failed_games: int = 0
