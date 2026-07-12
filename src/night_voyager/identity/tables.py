from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class Actor(Base):
    __tablename__ = "actors"
    __table_args__ = (UniqueConstraint("organization_id", "id"), {"schema": "app"})

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app.organizations.id")
    )
    display_name: Mapped[str] = mapped_column(String)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "actor_id", "role"),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    actor_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    role: Mapped[str] = mapped_column(String)
