from app import usecases
from app.exceptions import NotFound
from app.schemas import SnapshotResponse
from app.usecase_handlers.base import DatabaseHandler


class GetPriceHistoryHandler(DatabaseHandler):
    def handle(self, usecase: usecases.GetPriceHistoryUseCase) -> list[SnapshotResponse]:
        with self.transaction() as repositories:
            if repositories.games.get(usecase.game_id) is None:
                raise NotFound("Game not found in local catalog; look up its details first")
            return [
                SnapshotResponse.model_validate(row)
                for row in repositories.games.history(
                    usecase.game_id, usecase.limit, usecase.offset
                )
            ]
