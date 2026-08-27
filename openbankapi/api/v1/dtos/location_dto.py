"""Location DTOs."""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class LocationCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class LocationUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[Name] = None
    active: Optional[bool] = None


class LocationResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    active: bool
