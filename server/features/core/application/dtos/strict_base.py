from pydantic import BaseModel


class StrictBaseModel(BaseModel):
    model_config = {"extra": "forbid"}
