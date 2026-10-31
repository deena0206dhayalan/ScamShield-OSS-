from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CallLog(SQLModel, table=True):
    """One analysed call snippet (audit trail)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=_now)
    transcript: str
    coercion_score: int
    status: str
    bns_violation: Optional[str] = None


class EvidenceRecord(SQLModel, table=True):
    """One scanned document (evidence vault)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=_now)
    file_name: str
    risk_score: int
    verdict: str
    counter_notice: str
