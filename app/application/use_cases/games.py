from app.application.exceptions import NotFound
from app.application.ports import PriceProvider, UnitOfWork
from app.application.use_cases.shared import GameRefresher
from app.domain.entities import Game, PriceSnapshot


class SearchGames:
    def __init__(self, uow: UnitOfWork, provider: PriceProvider):
        self.uow = uow
        self.provider = provider

    def execute(self, query: str, limit: int = 20) -> list[Game]:
        results = self.provider.search(query, limit)
        # Consistent lock ordering across overlapping searches and watchlist refreshes.
        saved = {
            game.id: self.uow.games.save_metadata(game)
            for game in sorted(results, key=lambda game: game.id)
        }
        self.uow.commit()
        return [saved[game.id] for game in results]


class GetGame:
    def __init__(self, uow: UnitOfWork, provider: PriceProvider, cache_ttl_seconds: int):
        self.uow = uow
        self.refresher = GameRefresher(uow, provider, cache_ttl_seconds)

    def execute(self, game_id: str) -> Game:
        game, _, _ = self.refresher.refresh(game_id)
        self.uow.commit()
        return game


class GetPriceHistory:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def execute(self, game_id: str, limit: int = 100, offset: int = 0) -> list[PriceSnapshot]:
        if self.uow.games.get(game_id) is None:
            raise NotFound("Game not found in local catalog; look up its details first")
        return self.uow.games.history(game_id, limit, offset)
