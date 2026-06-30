from types import SimpleNamespace

import pytest

from app.models import SourceRegistry
from app.schemas import CatalogImportRequest
from app.services import catalog_imports


def source(config: dict, *, active: bool = True) -> SourceRegistry:
    return SourceRegistry(
        key="TEST_SOURCE",
        name="Test source",
        category="TEST",
        implementation_status="IMPLEMENTED",
        access_mode="AUTOMATIC",
        description="Test",
        import_mode="AUTOMATIC",
        service_type="WFS",
        service_url="https://example.test/wfs",
        adapter_config=config,
        is_active=active,
    )


def test_bbox_axis_order_is_profile_specific():
    bbox = [19.18, 49.67, 19.20, 49.69]
    assert catalog_imports._bbox_value(bbox, {"axis_order": "xy", "bbox_crs": "EPSG:4326"}) == "19.18,49.67,19.2,49.69,EPSG:4326"
    assert catalog_imports._bbox_value(bbox, {"axis_order": "yx", "bbox_crs": "EPSG:4326"}) == "49.67,19.18,49.69,19.2,EPSG:4326"


def test_capabilities_parser_reads_version_and_layers():
    xml = b"""<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs/2.0" version="2.0.0"><wfs:FeatureTypeList><wfs:FeatureType><wfs:Name>ms:dzialki</wfs:Name></wfs:FeatureType></wfs:FeatureTypeList></wfs:WFS_Capabilities>"""
    version, names = catalog_imports._feature_type_names(xml)
    assert version == "2.0.0"
    assert names == ["ms:dzialki"]


def test_area_preset_resolves_without_user_coordinates():
    payload = CatalogImportRequest(source_key="TEST_SOURCE", area_preset_key="ZYWIEC_CENTER_SAMPLE")
    assert catalog_imports.resolve_bbox(payload) == [19.18, 49.67, 19.20, 49.69]


def test_preview_blocks_feature_count_over_limit(monkeypatch):
    config = {
        "version": "2.0.0",
        "typename": "test:layer",
        "axis_order": "xy",
        "bbox_crs": "EPSG:4326",
        "type_name_parameter": "typeNames",
        "hits_attribute": "numberMatched",
    }
    response = SimpleNamespace(
        content=b'<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" numberMatched="20001"/>',
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr(catalog_imports.httpx, "get", lambda *args, **kwargs: response)
    result = catalog_imports.preview_catalog_import(source(config), [19.18, 49.67, 19.20, 49.69])
    assert result.allowed is False
    assert result.estimated_feature_count == 20001
    assert "przekracza limit" in result.warnings[0]


def test_preview_honors_stricter_source_limit(monkeypatch):
    config = {
        "version": "2.0.0",
        "typename": "test:layer",
        "axis_order": "xy",
        "bbox_crs": "EPSG:4326",
        "type_name_parameter": "typeNames",
        "hits_attribute": "numberMatched",
        "feature_limit": 1000,
    }
    response = SimpleNamespace(
        content=b'<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" numberMatched="1001"/>',
        raise_for_status=lambda: None,
    )
    monkeypatch.setattr(catalog_imports.httpx, "get", lambda *args, **kwargs: response)
    result = catalog_imports.preview_catalog_import(
        source(config), [19.18, 49.67, 19.20, 49.69]
    )
    assert result.allowed is False
    assert result.feature_limit == 1000


def test_preview_rejects_inactive_catalog_source():
    with pytest.raises(Exception) as error:
        catalog_imports.preview_catalog_import(source({"version": "2.0.0"}, active=False), [19.18, 49.67, 19.20, 49.69])
    assert getattr(error.value, "status_code", None) == 422


def test_page_plan_covers_complete_server_limited_result():
    assert catalog_imports._page_plan({"page_size": 1000}, 3814, 20_000) == [
        (0, 1000),
        (1000, 1000),
        (2000, 1000),
        (3000, 814),
    ]
    assert catalog_imports._page_plan({}, 3814, 20_000) == [(None, 20_001)]
