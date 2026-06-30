"""Initial GeoHarmonizer schema and registries."""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_DEFAULT = sa.text("'{}'::jsonb")
NOW = sa.text("now()")


def _timestamps(updated: bool = False) -> list[sa.Column]:
    columns = [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW)]
    if updated:
        columns.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW))
    return columns


def _quote(value: object | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _json(value: object) -> str:
    return _quote(json.dumps(value, ensure_ascii=False)) + "::jsonb"


def upgrade() -> None:
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    except Exception as exc:
        raise RuntimeError("Nie można włączyć PostGIS/pgcrypto. Administrator PostgreSQL musi uruchomić CREATE EXTENSION postgis oraz pgcrypto.") from exc

    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email", sa.String(), nullable=False, unique=True), sa.Column("password_hash", sa.Text(), nullable=False), sa.Column("role", sa.String(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")), *_timestamps(updated=True))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("projects", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.Text(), nullable=False), sa.Column("description", sa.Text()), sa.Column("area_name", sa.Text()), sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False), *_timestamps(updated=True))
    op.create_table("data_sources", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.Text(), nullable=False), sa.Column("source_type", sa.String(), nullable=False), sa.Column("registry_key", sa.String()), sa.Column("url", sa.Text()), sa.Column("provider", sa.Text()), sa.Column("description", sa.Text()), sa.Column("legal_note", sa.Text()), *_timestamps())
    op.create_index("ix_data_sources_project_id", "data_sources", ["project_id"])
    op.create_table("dataset_imports", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("data_source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("data_sources.id", ondelete="SET NULL")), sa.Column("status", sa.String(), nullable=False), sa.Column("original_filename", sa.Text()), sa.Column("detected_format", sa.String()), sa.Column("detected_crs", sa.String()), sa.Column("target_crs", sa.String(), nullable=False, server_default="EPSG:2180"), sa.Column("feature_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("bbox", Geometry("POLYGON", srid=2180)), sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("error_message", sa.Text()), sa.Column("log_text", sa.Text()), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), *_timestamps())
    op.create_index("ix_dataset_imports_project_id", "dataset_imports", ["project_id"])
    op.create_table("layers", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("dataset_import_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("dataset_imports.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.Text(), nullable=False), sa.Column("layer_type", sa.String(), nullable=False), sa.Column("geometry_type", sa.String(), nullable=False), sa.Column("srid", sa.Integer(), nullable=False, server_default="2180"), sa.Column("attribute_schema", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("style_json", postgresql.JSONB()), sa.Column("is_visible_by_default", sa.Boolean(), nullable=False, server_default=sa.text("true")), *_timestamps())
    op.create_index("ix_layers_project_id", "layers", ["project_id"])
    op.create_index("ix_layers_dataset_import_id", "layers", ["dataset_import_id"])
    op.create_table("features", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("layer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("layers.id", ondelete="CASCADE"), nullable=False), sa.Column("external_id", sa.Text()), sa.Column("source_object_id", sa.Text()), sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("geom", Geometry("GEOMETRY", srid=2180), nullable=False), *_timestamps())
    op.create_index("ix_features_project_id", "features", ["project_id"])
    op.create_index("ix_features_layer_id", "features", ["layer_id"])
    op.create_index("ix_features_geom_gist", "features", ["geom"], postgresql_using="gist")
    op.create_table("analysis_definitions", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("key", sa.String(), nullable=False, unique=True), sa.Column("name", sa.Text(), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("input_requirements", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("parameters_schema", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), *_timestamps())
    op.create_table("analysis_runs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("analysis_key", sa.String(), nullable=False), sa.Column("name", sa.Text(), nullable=False), sa.Column("status", sa.String(), nullable=False), sa.Column("input_layer_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False), sa.Column("parameters_json", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("result_summary_json", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("error_message", sa.Text()), sa.Column("log_text", sa.Text()), sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)), *_timestamps())
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])
    op.create_table("analysis_results", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("result_type", sa.String(), nullable=False), sa.Column("severity", sa.String(), nullable=False), sa.Column("label", sa.Text(), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("recommendation", sa.Text(), nullable=False), sa.Column("metrics_json", postgresql.JSONB(), nullable=False, server_default=JSON_DEFAULT), sa.Column("feature_a_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("features.id", ondelete="SET NULL")), sa.Column("feature_b_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("features.id", ondelete="SET NULL")), sa.Column("geom", Geometry("GEOMETRY", srid=2180)), *_timestamps())
    op.create_index("ix_analysis_results_analysis_run_id", "analysis_results", ["analysis_run_id"])
    op.create_index("ix_analysis_results_project_id", "analysis_results", ["project_id"])
    op.create_index("ix_analysis_results_geom_gist", "analysis_results", ["geom"], postgresql_using="gist")
    op.create_table("event_logs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE")), sa.Column("entity_type", sa.String(), nullable=False), sa.Column("entity_id", postgresql.UUID(as_uuid=True)), sa.Column("level", sa.String(), nullable=False), sa.Column("message", sa.Text(), nullable=False), sa.Column("details_json", postgresql.JSONB()), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")), *_timestamps())
    op.create_index("ix_event_logs_project_id", "event_logs", ["project_id"])
    op.create_table("source_registry", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("key", sa.String(), nullable=False, unique=True), sa.Column("name", sa.Text(), nullable=False), sa.Column("category", sa.Text(), nullable=False), sa.Column("implementation_status", sa.String(), nullable=False), sa.Column("access_mode", sa.String(), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("limitations", sa.Text()), sa.Column("instruction_md", sa.Text()), *_timestamps())

    analysis_rows = [
        {"id": uuid.UUID("10000000-0000-0000-0000-000000000001"), "key": "BUILDING_PARCEL_RELATION", "name": "Budynki względem działek", "description": "Analiza relacji budynków względem działek.", "input_requirements": {"layer_buildings": "Polygon", "layer_parcels": "Polygon"}, "parameters_schema": {"tolerance_m": 0.1, "min_outside_area_m2": 1.0, "classify_touch_as_candidate": True}},
        {"id": uuid.UUID("10000000-0000-0000-0000-000000000002"), "key": "EGIB_LPIS_OVERLAP", "name": "Pokrycie EGiB–LPIS", "description": "Analiza pomocnicza pokrycia powierzchniowego EGiB i LPIS.", "input_requirements": {"layer_egib": "Polygon", "layer_lpis": "Polygon"}, "parameters_schema": {"min_intersection_area_m2": 1.0, "min_overlap_percent": 80.0, "sliver_area_threshold_m2": 5.0, "tolerance_m": 0.1}},
        {"id": uuid.UUID("10000000-0000-0000-0000-000000000003"), "key": "LINE_BOUNDARY_PROXIMITY", "name": "Linia–granica", "description": "Analiza zbliżenia dowolnej warstwy liniowej do granicy.", "input_requirements": {"layer_lines": "LineString", "layer_boundaries": "LineString|Polygon"}, "parameters_schema": {"tolerance_m": 0.3, "min_matching_length_m": 2.0, "min_matching_percent": 50.0}},
    ]
    for row in analysis_rows:
        op.execute(
            "INSERT INTO analysis_definitions (id, key, name, description, input_requirements, parameters_schema) VALUES "
            f"({_quote(row['id'])}, {_quote(row['key'])}, {_quote(row['name'])}, {_quote(row['description'])}, "
            f"{_json(row['input_requirements'])}, {_json(row['parameters_schema'])})"
        )

    rows = [
        ("FILE_GEOJSON", "Ręczny import GeoJSON", "Plik", "IMPLEMENTED", "MANUAL", "Import GeoJSON i JSON GeoJSON.", None),
        ("FILE_GPKG", "Ręczny import GeoPackage", "Plik", "PARTIAL", "MANUAL", "Import pierwszej warstwy wektorowej GeoPackage.", "Pozostałe warstwy są pomijane z ostrzeżeniem."),
        ("FILE_SHP_ZIP", "Ręczny import SHP ZIP", "Plik", "PARTIAL", "MANUAL", "Import pierwszego pliku SHP z bezpiecznego archiwum ZIP.", "Wymagany komplet plików SHP i definicja CRS."),
        ("FILE_GML", "Ręczny import GML", "Plik", "PARTIAL", "MANUAL", "Podstawowy import geometrii i atrybutów GML.", "Bez złożonych relacji modelu EGiB."),
        ("GENERIC_WFS", "WFS konfigurowany przez użytkownika", "Usługa", "PARTIAL", "BOTH", "Podstawowy GetCapabilities/GetFeature.", "Nietypowe formaty i konfiguracje osi mogą wymagać przygotowania pliku."),
        ("LPIS_WFS", "LPIS przez WFS", "LPIS", "PARTIAL", "BOTH", "Import z URL podanego przez użytkownika.", "Brak domyślnego publicznego URL."),
        ("LPIS_SHP", "LPIS jako paczka SHP", "LPIS", "PARTIAL", "MANUAL", "Import przez ogólny mechanizm SHP ZIP.", None),
        ("EGIB_WFS", "EGiB przez WFS", "EGiB", "PARTIAL", "BOTH", "Podstawowy import WFS.", "Dostępność i model usługi zależą od dostawcy."),
        ("BDOT500_GML", "BDOT500 jako GML z PZGiK", "BDOT500", "PLANNED", "MANUAL", "Planowane rozszerzenie obsługi modelu BDOT500.", None),
        ("BDOT500_WMS", "BDOT500 WMS", "BDOT500", "VIEW_ONLY", "VIEW_ONLY", "WMS może służyć wyłącznie do wizualizacji.", "Raster WMS nie nadaje się do analiz topologicznych."),
        ("ORTO_WMS_WCS", "Ortofotomapa", "Obraz", "PLANNED", "VIEW_ONLY", "Poza zakresem MVP.", None),
        ("LIDAR_LAZ", "LIDAR LAZ", "Chmura punktów", "PLANNED", "MANUAL", "Poza zakresem MVP.", None),
        ("GESUT_GML", "GESUT GML", "GESUT", "NOT_AVAILABLE_IN_MVP", "MANUAL", "Świadomie niedostępne w MVP.", None),
    ]
    for key, name, category, status, mode, description, limitations in rows:
        op.execute(
            "INSERT INTO source_registry (id, key, name, category, implementation_status, access_mode, description, limitations, instruction_md) VALUES "
            f"({_quote(uuid.uuid5(uuid.NAMESPACE_URL, f'geoharmonizer:{key}'))}, {_quote(key)}, {_quote(name)}, {_quote(category)}, {_quote(status)}, {_quote(mode)}, {_quote(description)}, {_quote(limitations)}, {_quote('Skonfiguruj źródło lub wgraj plik zgodnie z opisem.')})"
        )


def downgrade() -> None:
    for table in ["source_registry", "event_logs", "analysis_results", "analysis_runs", "analysis_definitions", "features", "layers", "dataset_imports", "data_sources", "projects", "users"]:
        op.drop_table(table)
