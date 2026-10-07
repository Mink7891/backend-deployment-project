from typing import Protocol

from app.domain.entities import ProviderGame


class PriceProvider(Protocol):
    source: str

    def search(self, query: str, limit: int = 20) -> list[ProviderGame]: ...

    def get_game(self, game_id: str) -> ProviderGame: ...
