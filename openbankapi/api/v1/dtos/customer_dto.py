"""Customer DTOs.

`date_of_birth` and `gender` carry `repr=False`: pydantic's generated repr
would otherwise print them, and a single `%r` in a log line is all it takes to
put a birth date on disk (spec §3.4).
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

IdentificationNumber = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class CustomerCreateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identification_number: IdentificationNumber
    first_name: Name
    last_name: Name
    date_of_birth: date = Field(repr=False)
    gender: Optional[str] = Field(default=None, max_length=20, repr=False)


class CustomerUpdateDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identification_number: Optional[IdentificationNumber] = None
    first_name: Optional[Name] = None
    last_name: Optional[Name] = None
    date_of_birth: Optional[date] = Field(default=None, repr=False)
    gender: Optional[str] = Field(default=None, max_length=20, repr=False)
    active: Optional[bool] = None


class CustomerResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    identification_number: str
    first_name: str
    last_name: str
    date_of_birth: date = Field(repr=False)
    gender: Optional[str] = Field(default=None, repr=False)
    # Derived on every read from date_of_birth; there is no age column (§3.4).
    age: int
    active: bool
    auth0_sub: Optional[str] = None


class CustomerAuth0LinkDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
