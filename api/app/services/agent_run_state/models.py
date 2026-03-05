"""ORM model for agent run state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AgentRunStateRecord(Base):
    __tablename__ = "agent_run_state"

    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    worker_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    branch: Mapped[str] = mapped_column(String, nullable=False, default="")
    repo_path: Mapped[str] = mapped_column(String, nullable=False, default="")
    head_sha: Mapped[str] = mapped_column(String, nullable=False, default="")
    checkpoint_sha: Mapped[str] = mapped_column(String, nullable=False, default="")
    failure_class: Mapped[str] = mapped_column(String, nullable=False, default="")
    next_action: Mapped[str] = mapped_column(String, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
