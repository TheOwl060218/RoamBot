"""Server-owned places, editable date assignments, explicit route regeneration."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CreateItinerary(Contract):
    name: str = Field(min_length=1, max_length=100)


class Versioned(Contract):
    version: int = Field(ge=1)


class EditItinerary(Versioned):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    travel_mode: Literal['walking', 'bicycling', 'driving'] | None = None
    @model_validator(mode='after')
    def dates(self):
        if bool(self.start_date) != bool(self.end_date):
            raise ValueError('请选择完整的出行日期。')
        if self.start_date and not 0 <= (self.end_date - self.start_date).days < 30:
            raise ValueError('行程日期需按先后顺序，最多30天。')
        return self


class AddStop(Contract):
    source_job_id: str | None = Field(default=None, max_length=64)
    history_id: str | None = Field(default=None, max_length=100)
    favorite_id: str | None = Field(default=None, max_length=100)
    place_id: str | None = Field(default=None, max_length=255)
    @model_validator(mode='after')
    def source(self):
        if sum(bool(v) for v in (self.source_job_id, self.history_id, self.favorite_id)) != 1:
            raise ValueError('请选择一个真实推荐或收藏来源。')
        if not self.favorite_id and not self.place_id:
            raise ValueError('请选择来源中的地点。')
        return self


class TransferStop(Versioned):
    target_id: str = Field(min_length=1, max_length=100)


class DayOrder(Contract):
    date: date
    stop_ids: list[str] = Field(default_factory=list, max_length=60)


class SaveOrder(Versioned):
    days: list[DayOrder] = Field(max_length=30)
    unassigned_ids: list[str] = Field(default_factory=list, max_length=60)


class GenerateRoute(Versioned):
    request_id: str = Field(min_length=16, max_length=100)
    optimize: bool = False
