import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UpdatedTimestampMixin(TimestampMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, UpdatedTimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Project(Base, UpdatedTimestampMixin):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    area_name: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    registry_key: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    legal_note: Mapped[str | None] = mapped_column(Text)


class DatasetImport(Base, TimestampMixin):
    __tablename__ = "dataset_imports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    original_filename: Mapped[str | None] = mapped_column(Text)
    detected_format: Mapped[str | None] = mapped_column(String)
    detected_crs: Mapped[str | None] = mapped_column(String)
    target_crs: Mapped[str] = mapped_column(String, default="EPSG:2180")
    feature_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bbox: Mapped[Any | None] = mapped_column(Geometry("POLYGON", srid=2180))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    error_message: Mapped[str | None] = mapped_column(Text)
    log_text: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Layer(Base, TimestampMixin):
    __tablename__ = "layers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    dataset_import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_imports.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    layer_type: Mapped[str] = mapped_column(String, nullable=False)
    geometry_type: Mapped[str] = mapped_column(String, nullable=False)
    srid: Mapped[int] = mapped_column(Integer, default=2180, server_default="2180")
    attribute_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    style_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_visible_by_default: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Feature(Base, TimestampMixin):
    __tablename__ = "features"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    layer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("layers.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(Text)
    source_object_id: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    geom: Mapped[Any] = mapped_column(Geometry("GEOMETRY", srid=2180), nullable=False)

    __table_args__ = (Index("ix_features_geom_gist", "geom", postgresql_using="gist"),)


class AnalysisDefinition(Base, TimestampMixin):
    __tablename__ = "analysis_definitions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_requirements: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    parameters_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")


class AnalysisRun(Base, TimestampMixin):
    __tablename__ = "analysis_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    analysis_key: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    input_layer_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    result_summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    error_message: Mapped[str | None] = mapped_column(Text)
    log_text: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisResult(Base, TimestampMixin):
    __tablename__ = "analysis_results"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    result_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    feature_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="SET NULL")
    )
    feature_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id", ondelete="SET NULL")
    )
    geom: Mapped[Any | None] = mapped_column(Geometry("GEOMETRY", srid=2180))

    __table_args__ = (Index("ix_analysis_results_geom_gist", "geom", postgresql_using="gist"),)


class EventLog(Base, TimestampMixin):
    __tablename__ = "event_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    level: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class SourceRegistry(Base, TimestampMixin):
    __tablename__ = "source_registry"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    implementation_status: Mapped[str] = mapped_column(String, nullable=False)
    access_mode: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str | None] = mapped_column(Text)
    instruction_md: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    service_type: Mapped[str | None] = mapped_column(String)
    service_url: Mapped[str | None] = mapped_column(Text)
    documentation_url: Mapped[str | None] = mapped_column(Text)
    import_mode: Mapped[str] = mapped_column(String, default="MANUAL_UPLOAD", server_default="MANUAL_UPLOAD")
    dataset_version: Mapped[str | None] = mapped_column(String)
    default_layer_type: Mapped[str | None] = mapped_column(String)
    geometry_type: Mapped[str | None] = mapped_column(String)
    geographic_scope: Mapped[str | None] = mapped_column(Text)
    legal_note: Mapped[str | None] = mapped_column(Text)
    adapter_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_status: Mapped[str | None] = mapped_column(String)
    last_check_message: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
