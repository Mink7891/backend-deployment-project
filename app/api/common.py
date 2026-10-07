from typing import Annotated

from fastapi import Path, Query

PositiveId = Annotated[int, Path(ge=1)]
PageLimit = Annotated[int, Query(ge=1, le=500)]
PageOffset = Annotated[int, Query(ge=0)]
