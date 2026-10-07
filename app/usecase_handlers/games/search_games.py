from app import usecases
from app.schemas import GameCard
from app.usecase_handlers.base import DatabaseHandler


class SearchGamesHandler(DatabaseHandler):
    def handle(self, usecase: usecases.SearchGamesUseCase) -> list[GameCard]:
        results = self.provider.search(usecase.query, usecase.limit)
        with self.transaction() as repositories:
            # The same ordering as refresh avoids lock inversions between overlapping searches.
            saved = {
                game.id: repositories.games.save_metadata(game)
                for game in sorted(results, key=lambda game: game.id)
            }
            return [GameCard.model_validate(saved[game.id]) for game in results]
