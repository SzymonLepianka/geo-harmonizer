import uuid

import geopandas as gpd
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from shapely.geometry import Polygon, box

from app.dependencies import require_editor
from app.models import User
from app.schemas import CatalogImportRequest
from app.services.imports import _normalize_frame


def test_viewer_cannot_edit():
    viewer = User(id=uuid.uuid4(), email="viewer@example.com", password_hash="x", role="VIEWER", is_active=True)
    with pytest.raises(HTTPException) as error:
        require_editor(viewer)
    assert error.value.status_code == 403


def test_admin_can_edit():
    admin = User(id=uuid.uuid4(), email="admin@example.com", password_hash="x", role="ADMIN", is_active=True)
    assert require_editor(admin) is admin


def test_catalog_import_rejects_invalid_bbox():
    with pytest.raises(ValidationError):
        CatalogImportRequest(source_key="TEST", bbox=[19.2, 49.7, 19.1, 49.8])


def test_geojson_without_crs_is_assumed_wgs84_and_transformed():
    frame = gpd.GeoDataFrame({"name": ["test"]}, geometry=[box(19.0, 52.0, 19.01, 52.01)])
    normalized, detected = _normalize_frame(frame, "GeoJSON", [])
    assert detected == "EPSG:4326"
    assert normalized.crs.to_epsg() == 2180


def test_invalid_geometry_is_repaired():
    bowtie = Polygon([(0, 0), (2, 2), (0, 2), (2, 0), (0, 0)])
    frame = gpd.GeoDataFrame({"name": ["test"]}, geometry=[bowtie], crs="EPSG:2180")
    logs: list[str] = []
    normalized, _ = _normalize_frame(frame, "GeoJSON", logs)
    assert normalized.geometry.iloc[0].is_valid
    assert any("naprawiono" in message for message in logs)
