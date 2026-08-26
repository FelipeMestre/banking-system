"""Customer DTOs.

`fecha_nacimiento` and `genero` carry `repr=False`: pydantic's generated repr
would otherwise print them, and a single `%r` in a log line is all it takes to
put a birth date on disk (spec §3.4).
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identificacion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ClienteCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero_identificacion: Identificacion
    nombre: Nombre
    apellido: Nombre
    fecha_nacimiento: date = Field(repr=False)
    genero: Optional[str] = Field(default=None, max_length=20, repr=False)


class ClienteUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numero_identificacion: Optional[Identificacion] = None
    nombre: Optional[Nombre] = None
    apellido: Optional[Nombre] = None
    fecha_nacimiento: Optional[date] = Field(default=None, repr=False)
    genero: Optional[str] = Field(default=None, max_length=20, repr=False)
    activo: Optional[bool] = None


class ClienteResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    numero_identificacion: str
    nombre: str
    apellido: str
    fecha_nacimiento: date = Field(repr=False)
    genero: Optional[str] = Field(default=None, repr=False)
    # Derived on every read from fecha_nacimiento; there is no age column (§3.4).
    age: int
    activo: bool
