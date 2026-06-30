import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=10, max_length=256)
    role: UserRole | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str | None = None
    area_name: str | None = Field(default=None, max_length=300)


class ProjectUpdate(ProjectCreate):
    pass


class ProjectOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    area_name: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    layer_count: int = 0
    analysis_count: int = 0


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    source_type: Literal["FILE_UPLOAD", "WFS", "MANUAL", "SAMPLE"]
    registry_key: str | None = None
    url: str | None = None
    provider: str | None = None
    description: str | None = None
    legal_note: str | None = None


class DataSourceOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: str
    registry_key: str | None
    url: str | None
    provider: str | None
    description: str | None
    legal_note: str | None
    created_at: datetime


class ImportOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    data_source_id: uuid.UUID | None
    status: str
    original_filename: str | None
    detected_format: str | None
    detected_crs: str | None
    target_crs: str
    feature_count: int
    metadata_json: dict[str, Any]
    error_message: str | None
    log_text: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CatalogImportRequest(BaseModel):
    source_key: str = Field(min_length=2, max_length=120)
    bbox: list[float] | None = None
    area_preset_key: str | None = None
    layer_name: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return value
        if len(value) != 4:
            raise ValueError("BBOX musi zawierać cztery współrzędne")
        min_lon, min_lat, max_lon, max_lat = value
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise ValueError("BBOX jest niepoprawny lub wykracza poza WGS84")
        return value


class LayerOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    dataset_import_id: uuid.UUID
    name: str
    layer_type: str
    geometry_type: str
    srid: int
    attribute_schema: dict[str, Any]
    style_json: dict[str, Any] | None
    is_visible_by_default: bool
    created_at: datetime
    feature_count: int = 0
    source_name: str | None = None


class AnalysisDefinitionOut(ORMModel):
    id: uuid.UUID
    key: str
    name: str
    description: str
    input_requirements: dict[str, Any]
    parameters_schema: dict[str, Any]
    created_at: datetime


class AnalysisRunCreate(BaseModel):
    analysis_key: str
    name: str | None = Field(default=None, max_length=300)
    inputs: dict[str, uuid.UUID]
    parameters: dict[str, float | bool] = Field(default_factory=dict)


class AnalysisRunOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    analysis_key: str
    name: str
    status: str
    input_layer_ids: list[uuid.UUID]
    parameters_json: dict[str, Any]
    result_summary_json: dict[str, Any]
    error_message: str | None
    log_text: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AnalysisResultOut(ORMModel):
    id: uuid.UUID
    analysis_run_id: uuid.UUID
    project_id: uuid.UUID
    result_type: str
    severity: str
    label: str
    description: str
    recommendation: str
    metrics_json: dict[str, Any]
    feature_a_id: uuid.UUID | None
    feature_b_id: uuid.UUID | None
    created_at: datetime


class EventLogOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    level: str
    message: str
    details_json: dict[str, Any] | None
    created_at: datetime
    user_id: uuid.UUID | None


class SourceRegistryOut(ORMModel):
    id: uuid.UUID
    key: str
    name: str
    category: str
    implementation_status: str
    access_mode: str
    description: str
    limitations: str | None
    instruction_md: str | None
    provider: str | None
    service_type: str | None
    service_url: str | None
    documentation_url: str | None
    import_mode: str
    dataset_version: str | None
    default_layer_type: str | None
    geometry_type: str | None
    geographic_scope: str | None
    legal_note: str | None
    adapter_config: dict[str, Any]
    is_active: bool
    sort_order: int
    last_verified_at: datetime | None
    last_check_status: str | None
    last_check_message: str | None
    last_checked_at: datetime | None
    created_at: datetime


class CatalogCheckOut(BaseModel):
    key: str
    status: str
    checked_at: datetime
    response_ms: int | None = None
    service_version: str | None = None
    available_layers: list[str] = Field(default_factory=list)
    message: str


class CatalogPreviewOut(BaseModel):
    source_key: str
    source_name: str
    bbox: list[float]
    estimated_feature_count: int | None
    feature_limit: int
    allowed: bool
    warnings: list[str] = Field(default_factory=list)


class AreaPresetOut(BaseModel):
    key: str
    name: str
    description: str
    bbox: list[float]
