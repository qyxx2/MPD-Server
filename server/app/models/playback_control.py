from pydantic import BaseModel, ConfigDict, Field


class PlaybackControlTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    queue_item_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
