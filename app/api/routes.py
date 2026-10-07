"""HTTP entry points; authentication is shared across domain routers."""

from fastapi import APIRouter, Depends

from app.api import games, items, notifications, watchlists
from app.api.dependencies import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])
for domain_router in (games.router, watchlists.router, items.router, notifications.router):
    router.include_router(domain_router)
