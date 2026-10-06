from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.api.dependencies import (
    ProviderDependency,
    SettingsDependency,
    UowDependency,
    require_api_key,
)
from app.api.presenters import present_game, present_item, present_watchlist
from app.api.schemas import (
    AddItemRequest,
    CreateWatchlistRequest,
    GameCard,
    GameDetails,
    GameId,
    ItemResponse,
    NotificationResponse,
    RefreshResponse,
    SnapshotResponse,
    SummaryResponse,
    UpdateItemRequest,
    WatchlistDetails,
    WatchlistResponse,
)
from app.application import use_cases

router = APIRouter(dependencies=[Depends(require_api_key)])
PositiveId = Annotated[int, Path(ge=1)]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("/games/search", response_model=list[GameCard], tags=["Games"])
def search_games(
    uow: UowDependency,
    provider: ProviderDependency,
    query: Annotated[str, Query(min_length=1, max_length=100, pattern=r".*\S.*")],
    limit: Annotated[int, Query(ge=1, le=60)] = 20,
):
    return use_cases.SearchGames(uow, provider).execute(query.strip(), limit)


@router.get("/games/{game_id}", response_model=GameDetails, tags=["Games"])
def get_game(
    game_id: GameId,
    uow: UowDependency,
    provider: ProviderDependency,
    settings: SettingsDependency,
):
    game = use_cases.GetGame(uow, provider, settings.refresh_min_interval_seconds).execute(game_id)
    return present_game(game)


@router.get("/games/{game_id}/history", response_model=list[SnapshotResponse], tags=["Games"])
def get_price_history(
    game_id: GameId,
    uow: UowDependency,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
):
    return use_cases.GetPriceHistory(uow).execute(game_id, limit, offset)


@router.post("/watchlists", response_model=WatchlistResponse, status_code=201, tags=["Watchlists"])
def create_watchlist(body: CreateWatchlistRequest, uow: UowDependency):
    return use_cases.CreateWatchlist(uow).execute(body.name)


@router.get("/watchlists", response_model=list[WatchlistResponse], tags=["Watchlists"])
def list_watchlists(uow: UowDependency):
    return use_cases.ListWatchlists(uow).execute()


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistDetails, tags=["Watchlists"])
def get_watchlist(watchlist_id: PositiveId, uow: UowDependency):
    return present_watchlist(use_cases.GetWatchlist(uow).execute(watchlist_id))


@router.delete("/watchlists/{watchlist_id}", status_code=204, tags=["Watchlists"])
def delete_watchlist(watchlist_id: PositiveId, uow: UowDependency):
    use_cases.DeleteWatchlist(uow).execute(watchlist_id)
    return Response(status_code=204)


@router.post(
    "/watchlists/{watchlist_id}/items", response_model=ItemResponse, status_code=201, tags=["Items"]
)
def add_watchlist_item(
    watchlist_id: PositiveId,
    body: AddItemRequest,
    uow: UowDependency,
    provider: ProviderDependency,
    settings: SettingsDependency,
):
    item = use_cases.AddWatchlistItem(uow, provider, settings.refresh_min_interval_seconds).execute(
        watchlist_id, body.game_id, body.target_price, body.steam_only
    )
    return present_item(item)


@router.patch(
    "/watchlists/{watchlist_id}/items/{item_id}", response_model=ItemResponse, tags=["Items"]
)
def update_watchlist_item(
    watchlist_id: PositiveId,
    item_id: PositiveId,
    body: UpdateItemRequest,
    uow: UowDependency,
    provider: ProviderDependency,
    settings: SettingsDependency,
):
    item = use_cases.UpdateWatchlistItem(
        uow, provider, settings.refresh_min_interval_seconds
    ).execute(watchlist_id, item_id, body.target_price, body.steam_only)
    return present_item(item)


@router.delete("/watchlists/{watchlist_id}/items/{item_id}", status_code=204, tags=["Items"])
def delete_watchlist_item(watchlist_id: PositiveId, item_id: PositiveId, uow: UowDependency):
    use_cases.DeleteWatchlistItem(uow).execute(watchlist_id, item_id)
    return Response(status_code=204)


@router.get(
    "/watchlists/{watchlist_id}/summary", response_model=SummaryResponse, tags=["Watchlists"]
)
def get_watchlist_summary(
    watchlist_id: PositiveId,
    uow: UowDependency,
    settings: SettingsDependency,
):
    return use_cases.GetWatchlistSummary(uow, settings.price_source).execute(watchlist_id)


@router.get(
    "/watchlists/{watchlist_id}/notifications",
    response_model=list[NotificationResponse],
    tags=["Notifications"],
)
def get_notifications(
    watchlist_id: PositiveId,
    uow: UowDependency,
    limit: PageLimit = 100,
    offset: PageOffset = 0,
):
    return use_cases.GetNotifications(uow).execute(watchlist_id, limit, offset)


@router.post(
    "/watchlists/{watchlist_id}/refresh", response_model=RefreshResponse, tags=["Watchlists"]
)
def refresh_watchlist(
    watchlist_id: PositiveId,
    uow: UowDependency,
    provider: ProviderDependency,
    settings: SettingsDependency,
):
    return use_cases.RefreshWatchlist(uow, provider, settings.refresh_min_interval_seconds).execute(
        watchlist_id
    )
