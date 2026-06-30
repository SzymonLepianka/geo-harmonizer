import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.enums import LAYER_TYPES, UserRole


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


class WFSImportRequest(BaseModel):
    url: str = Field(min_length=8)
    typename: str | None = None
    bbox: str | None = None
    layer_type: str
    layer_name: str = Field(min_length=1, max_length=300)
    source_name: str = Field(min_length=1, max_length=300)
    target_crs: str = "EPSG:2180"

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("WFS wymaga adresu HTTP lub HTTPS")
        return value

    @field_validator("layer_type")
    @classmethod
    def validate_layer_type(cls, value: str) -> str:
        if value not in LAYER_TYPES:
            raise ValueError("Nieobsługiwany typ warstwy")
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
    created_at: datetime

