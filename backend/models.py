"""SQLModel database models"""
from datetime import datetime
from sqlmodel import SQLModel, Field
from typing import Optional


class RequestLog(SQLModel, table=True):
    """Model for storing request logs"""
    __tablename__ = "requests"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    blocked: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    headers: Optional[str] = None
    body: Optional[str] = None
    matched_rule: Optional[str] = Field(default=None, index=True)

