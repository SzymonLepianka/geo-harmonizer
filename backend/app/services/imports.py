import hashlib
import math
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fiona
import geopandas as gpd
import httpx
import pandas as pd
from defusedxml import ElementTree
from fastapi import HTTPException, UploadFile
from geoalchemy2.shape import from_shape
from shapely import force_2d, make_valid
from shapely.geometry import box
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DatasetImport, DataSource, Feature, Layer, SourceRegistry
from app.services.events import add_event


class ImportFailure(ValueError):
    pass


def _safe_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _safe_value(value.item())
    return str(value)


def _safe_extract_zip(archive_path: Path, target: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        target_resolved = target.resolve()
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if target_resolved not in destination.parents and destination != target_resolved:
                raise ImportFailure("Archiwum ZIP zawiera niedozwoloną ścieżkę")
        archive.extractall(target)


def _format_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    formats = {".geojson": "GeoJSON", ".json": "GeoJSON", ".gpkg": "GPKG", ".gml": "GML", ".zip": "SHP_ZIP"}
    if suffix not in formats:
        raise ImportFailure("Obsługiwane formaty: GeoJSON, GPKG, SHP ZIP i podstawowy GML")
    return formats[suffix]


def _read_vector(path: Path, detected_format: str, logs: list[str]) -> gpd.GeoDataFrame:
    read_path = path
    if detected_format == "SHP_ZIP":
        extract_dir = path.parent / "shp"
        extract_dir.mkdir()
        _safe_extract_zip(path, extract_dir)
        shapefiles = sorted(extract_dir.rglob("*.shp"))
        if not shapefiles:
            raise ImportFailure("Archiwum nie zawiera pliku .shp")
        read_path = shapefiles[0]
        if len(shapefiles) > 1:
            logs.append("Ostrzeżenie: zaimportowano pierwszy SHP; pominięto: " + ", ".join(p.name for p in shapefiles[1:]))
    elif detected_format in {"GPKG", "GML"}:
        layers = list(fiona.listlayers(path))
        if not layers:
            raise ImportFailure("Plik nie zawiera warstwy wektorowej")
        if len(layers) > 1:
            logs.append("Ostrzeżenie: zaimportowano pierwszą warstwę; pominięto: " + ", ".join(layers[1:]))
        return gpd.read_file(path, layer=layers[0], engine="fiona")
    return gpd.read_file(read_path, engine="fiona")


def _geometry_type(gdf: gpd.GeoDataFrame) -> str:
    values = sorted(set(str(value) for value in gdf.geometry.geom_type.dropna()))
    if not values:
        return "Unknown"
    families = set()
    for value in values:
        if "Polygon" in value:
            families.add("Polygon")
        elif "Line" in value:
            families.add("LineString")
        elif "Point" in value:
            families.add("Point")
        else:
            families.add(value)
    return families.pop() if len(families) == 1 else "Mixed"


def _attribute_schema(gdf: gpd.GeoDataFrame) -> dict[str, Any]:
    return {column: str(dtype) for column, dtype in gdf.drop(columns=gdf.geometry.name).dtypes.items()}


def _normalize_frame(gdf: gpd.GeoDataFrame, detected_format: str, logs: list[str]) -> tuple[gpd.GeoDataFrame, str]:
    if gdf.empty:
        raise ImportFailure("Warstwa nie zawiera obiektów")
    if gdf.crs is None:
        if detected_format == "GeoJSON":
            gdf = gdf.set_crs(4326)
            logs.append("Brak deklaracji CRS w GeoJSON; przyjęto EPSG:4326 zgodnie z RFC 7946.")
        else:
            raise ImportFailure("Nie rozpoznano CRS. Uzupełnij definicję układu w pliku źródłowym.")
    detected_crs = gdf.crs.to_string()
    gdf = gdf[gdf.geometry.notna()].copy()
    if gdf.empty:
        raise ImportFailure("Warstwa nie zawiera geometrii")
    repaired = 0
    normalized = []
    for geom in gdf.geometry:
        geom = force_2d(geom)
        if not geom.is_valid:
            geom = make_valid(geom)
            repaired += 1
        normalized.append(geom)
    gdf.geometry = normalized
    gdf = gdf[~gdf.geometry.is_empty]
    if repaired:
        logs.append(f"Ostrzeżenie: naprawiono niepoprawne geometrie: {repaired}.")
    gdf = gdf.to_crs(2180)
    return gdf, detected_crs


def _persist_frame(
    db: Session,
    *,
    project_id: uuid.UUID,
    dataset_import: DatasetImport,
    gdf: gpd.GeoDataFrame,
    layer_name: str,
    layer_type: str,
    source_name: str,
) -> Layer:
    layer = Layer(
        project_id=project_id,
        dataset_import_id=dataset_import.id,
        name=layer_name,
        layer_type=layer_type,
        geometry_type=_geometry_type(gdf),
        srid=2180,
        attribute_schema=_attribute_schema(gdf),
    )
    db.add(layer)
    db.flush()
    attribute_columns = [column for column in gdf.columns if column != gdf.geometry.name]
    id_candidates = [column for column in attribute_columns if column.lower() in {"id", "fid", "gml_id", "identifier"}]
    for index, row in gdf.iterrows():
        attributes = {column: _safe_value(row[column]) for column in attribute_columns}
        external_id = str(row[id_candidates[0]]) if id_candidates and row[id_candidates[0]] is not None else None
        db.add(
            Feature(
                project_id=project_id,
                layer_id=layer.id,
                external_id=external_id,
                source_object_id=str(index),
                attributes=attributes,
                geom=from_shape(row.geometry, srid=2180),
            )
        )
    minx, miny, maxx, maxy = gdf.total_bounds
    dataset_import.feature_count = len(gdf)
    dataset_import.bbox = from_shape(box(minx, miny, maxx, maxy), srid=2180)
    dataset_import.metadata_json = {
        **dataset_import.metadata_json,
        "layer_name": layer_name,
        "source_name": source_name,
        "columns": attribute_columns,
        "geometry_type": layer.geometry_type,
        "bbox_2180": [minx, miny, maxx, maxy],
    }
    return layer


def _create_import_records(
    db: Session,
    *,
    project_id: uuid.UUID,
    source_name: str,
    source_type: str,
    registry_key: str,
    original_filename: str | None,
    url: str | None = None,
) -> tuple[DataSource, DatasetImport]:
    source = DataSource(project_id=project_id, name=source_name, source_type=source_type, registry_key=registry_key, url=url)
    db.add(source)
    db.flush()
    record = DatasetImport(project_id=project_id, data_source_id=source.id, status="PENDING", original_filename=original_filename, target_crs="EPSG:2180", metadata_json={})
    db.add(record)
    db.commit()
    return source, record


def import_uploaded_file(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    upload: UploadFile,
    layer_type: str,
    layer_name: str,
    source_name: str,
    target_crs: str,
    catalog_source: SourceRegistry | None = None,
) -> tuple[DatasetImport, Layer]:
    if target_crs.upper() != "EPSG:2180":
        raise HTTPException(status_code=422, detail="MVP zapisuje dane wyłącznie w EPSG:2180")
    filename = Path(upload.filename or "upload").name
    source, record = _create_import_records(
        db,
        project_id=project_id,
        source_name=source_name,
        source_type="FILE_UPLOAD",
        registry_key=catalog_source.key if catalog_source else "FILE_UPLOAD",
        original_filename=filename,
        url=catalog_source.service_url if catalog_source else None,
    )
    if catalog_source:
        source.provider = catalog_source.provider
        source.description = catalog_source.description
        source.legal_note = catalog_source.legal_note
    logs: list[str] = []
    try:
        detected_format = _format_for_path(Path(filename))
        if not catalog_source:
            source.registry_key = {
                "GeoJSON": "FILE_GEOJSON",
                "GPKG": "FILE_GPKG",
                "SHP_ZIP": "FILE_SHP_ZIP",
                "GML": "FILE_GML",
            }[detected_format]
        record.status = "RUNNING"
        record.started_at = datetime.now(UTC)
        record.detected_format = detected_format
        db.commit()
        with tempfile.TemporaryDirectory(prefix="geoharmonizer-") as temp:
            path = Path(temp) / filename
            digest = hashlib.sha256()
            upload_size = 0
            with path.open("wb") as destination:
                while chunk := upload.file.read(1024 * 1024):
                    upload_size += len(chunk)
                    if upload_size > get_settings().max_upload_mb * 1024 * 1024:
                        raise ImportFailure("Plik przekracza skonfigurowany limit rozmiaru")
                    digest.update(chunk)
                    destination.write(chunk)
            record.metadata_json = {
                "upload_size_bytes": upload_size,
                "sha256": digest.hexdigest(),
                "original_filename": filename,
                "source_catalog_key": catalog_source.key if catalog_source else None,
                "dataset_version": catalog_source.dataset_version if catalog_source else None,
                "last_verified_at": catalog_source.last_verified_at.isoformat()
                if catalog_source and catalog_source.last_verified_at
                else None,
            }
            gdf = _read_vector(path, detected_format, logs)
            gdf, detected_crs = _normalize_frame(gdf, detected_format, logs)
            record = db.get(DatasetImport, record.id)
            record.detected_crs = detected_crs
            layer = _persist_frame(db, project_id=project_id, dataset_import=record, gdf=gdf, layer_name=layer_name, layer_type=layer_type, source_name=source_name)
            record.status = "DONE"
            record.finished_at = datetime.now(UTC)
            record.log_text = "\n".join(["Import zakończony.", *logs])
            add_event(db, project_id=project_id, entity_type="dataset_import", entity_id=record.id, user_id=user_id, message=f"Zaimportowano warstwę „{layer_name}” ({len(gdf)} obiektów).", details={"warnings": logs})
            db.commit()
            db.refresh(record)
            db.refresh(layer)
            return record, layer
    except Exception as exc:
        db.rollback()
        record = db.get(DatasetImport, record.id)
        record.status = "ERROR"
        record.error_message = str(exc)
        record.log_text = "\n".join([*logs, f"Import przerwany: {exc}"])
        record.finished_at = datetime.now(UTC)
        add_event(db, project_id=project_id, entity_type="dataset_import", entity_id=record.id, user_id=user_id, level="ERROR", message="Import nie został zakończony.", details={"reason": str(exc)})
        db.commit()
        raise HTTPException(status_code=422, detail={"message": str(exc), "import_id": str(record.id)}) from exc


def _discover_typename(url: str) -> str:
    settings = get_settings()
    response = httpx.get(url, params={"service": "WFS", "request": "GetCapabilities"}, timeout=settings.wfs_timeout_seconds)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    names = []
    for element in root.iter():
        if element.tag.split("}")[-1] == "FeatureType":
            for child in element:
                if child.tag.split("}")[-1] == "Name" and child.text:
                    names.append(child.text)
                    break
    if len(names) != 1:
        raise ImportFailure("WFS udostępnia wiele warstw. Podaj typename. Dostępne: " + ", ".join(names[:30]))
    return names[0]


def import_wfs(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    url: str,
    typename: str | None,
    bbox: str | None,
    layer_type: str,
    layer_name: str,
    source_name: str,
    target_crs: str,
) -> tuple[DatasetImport, Layer]:
    if target_crs.upper() != "EPSG:2180":
        raise HTTPException(status_code=422, detail="MVP zapisuje dane wyłącznie w EPSG:2180")
    source, record = _create_import_records(db, project_id=project_id, source_name=source_name, source_type="WFS", registry_key="GENERIC_WFS", original_filename=None, url=url)
    logs: list[str] = []
    try:
        record.status = "RUNNING"
        record.started_at = datetime.now(UTC)
        db.commit()
        typename = typename or _discover_typename(url)
        params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": typename, "outputFormat": "application/json", "srsName": "EPSG:4326"}
        if bbox:
            parts = [float(part.strip()) for part in bbox.split(",")]
            if len(parts) != 4:
                raise ImportFailure("BBOX musi mieć postać minLon,minLat,maxLon,maxLat")
            params["bbox"] = bbox + ",EPSG:4326"
        settings = get_settings()
        response = httpx.get(url, params=params, timeout=settings.wfs_timeout_seconds)
        response.raise_for_status()
        if len(response.content) > settings.max_wfs_mb * 1024 * 1024:
            raise ImportFailure("Odpowiedź WFS przekracza skonfigurowany limit")
        with tempfile.TemporaryDirectory(prefix="geoharmonizer-wfs-") as temp:
            content_type = response.headers.get("content-type", "")
            extension = ".geojson" if "json" in content_type or response.content.lstrip().startswith(b"{") else ".gml"
            path = Path(temp) / f"wfs{extension}"
            path.write_bytes(response.content)
            detected = "GeoJSON" if extension == ".geojson" else "GML"
            try:
                gdf = _read_vector(path, detected, logs)
            except Exception:
                if extension == ".geojson":
                    params.pop("outputFormat", None)
                    response = httpx.get(url, params=params, timeout=settings.wfs_timeout_seconds)
                    response.raise_for_status()
                    path = Path(temp) / "wfs.gml"
                    path.write_bytes(response.content)
                    detected = "GML"
                    gdf = _read_vector(path, detected, logs)
                else:
                    raise
            gdf, detected_crs = _normalize_frame(gdf, detected, logs)
            record = db.get(DatasetImport, record.id)
            record.detected_format = f"WFS/{detected}"
            record.detected_crs = detected_crs
            record.metadata_json = {"url": url, "typename": typename, "bbox_request": bbox}
            layer = _persist_frame(db, project_id=project_id, dataset_import=record, gdf=gdf, layer_name=layer_name, layer_type=layer_type, source_name=source_name)
            record.status = "DONE"
            record.finished_at = datetime.now(UTC)
            record.log_text = "\n".join(["Import WFS zakończony.", *logs])
            add_event(db, project_id=project_id, entity_type="dataset_import", entity_id=record.id, user_id=user_id, message=f"Zaimportowano WFS „{layer_name}” ({len(gdf)} obiektów).")
            db.commit()
            db.refresh(record)
            db.refresh(layer)
            return record, layer
    except Exception as exc:
        db.rollback()
        record = db.get(DatasetImport, record.id)
        record.status = "ERROR"
        record.error_message = str(exc)
        record.log_text = "\n".join([*logs, f"Import WFS przerwany: {exc}"])
        record.finished_at = datetime.now(UTC)
        add_event(db, project_id=project_id, entity_type="dataset_import", entity_id=record.id, user_id=user_id, level="ERROR", message="Import WFS nie został zakończony.", details={"reason": str(exc)})
        db.commit()
        raise HTTPException(status_code=422, detail={"message": str(exc), "import_id": str(record.id)}) from exc
