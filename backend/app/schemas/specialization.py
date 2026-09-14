from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SpecializationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
