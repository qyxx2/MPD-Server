from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Playlist(BaseModel):
    playlist_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    is_system: bool = False
