"""Precise reusable scalar types for generated request models and route parameters."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints

GameId = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,32}$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
