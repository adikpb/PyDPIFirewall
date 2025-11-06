"""SQLModel database models"""

from datetime import datetime
from sqlmodel import SQLModel, Field


class RequestLog(SQLModel, table=True):
    """Model for storing request logs"""

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    blocked: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.now)
    headers: str | None = None
    body: str | None = None
    matched_rule: str | None = Field(default=None, index=True)
