"""Branch DTOs."""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Code = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True,
                                          min_length=1, max_length=10)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class BranchCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Code
    name: Name
    location_id: UUID


class BranchUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Optional[Code] = None
    name: Optional[Name] = None
    location_id: Optional[UUID] = None
    active: Optional[bool] = None


class BranchResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    location_id: UUID
    active: bool
