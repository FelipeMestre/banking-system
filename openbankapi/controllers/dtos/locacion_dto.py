"""Location DTOs."""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class LocacionCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Nombre


class LocacionUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Optional[Nombre] = None


class LocacionResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
