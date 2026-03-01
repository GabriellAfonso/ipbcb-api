from core.application.dtos.strict_base import StrictBaseModel
from pydantic import Field, field_validator
from typing import Optional
from pydantic import EmailStr


class RegisterDTO(StrictBaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=6)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip().lower()

class LoginDTO(StrictBaseModel):
    username: str = Field(..., min_length=1, max_length=150)
    password: str = Field(..., min_length=1)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return v.strip().lower()


class TokenDTO(StrictBaseModel):
    access: str
    refresh: Optional[str] = None
