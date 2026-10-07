"""Handwritten configuration and cross-field rules inherited by generated DTOs."""

from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic.alias_generators import to_camel


class DTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        alias_generator=to_camel,
        extra="forbid",
    )


class CreateWatchlistRequestBase(DTO):
    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UpdateItemRequestBase(DTO):
    @model_validator(mode="after")
    def require_patch_fields(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide target_price or steam_only")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Patch fields cannot be null")
        return self
