"""Branch DTOs."""
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Codigo = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True,
                                          min_length=1, max_length=10)]
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SucursalCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: Codigo
    nombre: Nombre
    locacion_id: UUID


class SucursalUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo: Optional[Codigo] = None
    nombre: Optional[Nombre] = None
    locacion_id: Optional[UUID] = None
    activa: Optional[bool] = None


class SucursalResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str
    nombre: str
    locacion_id: UUID
    activa: bool
