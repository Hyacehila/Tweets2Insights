from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, AwareDatetime

Identifier = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')]
UTCDateTime = Annotated[AwareDatetime, AfterValidator(lambda v: v.astimezone(timezone.utc))]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', validate_assignment=True)
    contract_version: Literal['1'] = '1'
