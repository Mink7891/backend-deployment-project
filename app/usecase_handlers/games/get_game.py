from app import usecases
from app.mappers.responses import present_game
from app.schemas import GameDetails
from app.usecase_handlers.base import DatabaseHandler


class GetGameHandler(DatabaseHandler):
    def handle(self, usecase: usecases.GetGameUseCase) -> GameDetails:
        with self.transaction() as repositories:
            game, _, _ = self.refresh_service.refresh(repositories, usecase.game_id)
            return present_game(game)
