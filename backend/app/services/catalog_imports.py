from __future__ import annotations

import hashlib
import tempfile
import time
import uuid
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx
import pandas as pd
from defusedxml import ElementTree
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DatasetImport, SourceRegistry
from app.schemas import CatalogCheckOut, CatalogImportRequest, CatalogPreviewOut
from app.services.events import add_event
from app.services.imports import (
    ImportFailure,
    _create_import_records,
    _normalize_frame,
    _persist_frame,
    _read_vector,
)

AREA_PRESETS = {
    "ZYWIEC_CENTER_SAMPLE": {
        "key": "ZYWIEC_CENTER_SAMPLE",
        "name": "Żywiec — centrum, próbka ok. 2×2 km",
        "description": "Prostokąt badawczy, nie granica administracyjna powiatu.",
        "bbox": [19.18, 49.67, 19.20, 49.69],
    }
}


def resolve_bbox(payload: CatalogImportRequest) -> list[float]:
    if payload.area_preset_key:
        preset = AREA_PRESETS.get(payload.area_preset_key)
        if not preset:
            raise HTTPException(status_code=422, detail="Nieznany preset obszaru")
        return list(preset["bbox"])
    if payload.bbox:
        return payload.bbox
    raise HTTPException(status_code=422, detail="Wybierz obszar na mapie albo użyj presetu")


def get_catalog_source(db: Session, key: str) -> SourceRegistry:
    source = db.query(SourceRegistry).filter(SourceRegistry.key == key).one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Nie znaleziono źródła w katalogu")
    return source


def _config(source: SourceRegistry) -> dict[str, Any]:
    config = source.adapter_config or {}
    if source.service_type != "WFS" or not source.service_url or not config.get("version"):
        raise HTTPException(status_code=422, detail="Źródło nie ma kompletnego profilu automatycznego importu")
    return config


def _typename_parameters(config: dict[str, Any]) -> dict[str, str]:
    typename = config.get("typename")
    if not typename:
        raise HTTPException(status_code=422, detail="Źródło nie definiuje warstwy WFS")
    return {config.get("type_name_parameter", "typeNames"): typename}


def _bbox_value(bbox: list[float], config: dict[str, Any]) -> str:
    min_lon, min_lat, max_lon, max_lat = bbox
    values = (
        [min_lat, min_lon, max_lat, max_lon]
        if config.get("axis_order") == "yx"
        else [min_lon, min_lat, max_lon, max_lat]
    )
    return ",".join(str(value) for value in values) + f",{config.get('bbox_crs', 'EPSG:4326')}"


def _base_params(source: SourceRegistry, bbox: list[float]) -> dict[str, str]:
    config = _config(source)
    params = {
        "service": "WFS",
        "version": str(config["version"]),
        "request": "GetFeature",
        "srsName": str(config.get("bbox_crs", "EPSG:4326")),
        "bbox": _bbox_value(bbox, config),
        **_typename_parameters(config),
    }
    return params


def _feature_type_names(content: bytes) -> tuple[str | None, list[str]]:
    root = ElementTree.fromstring(content)
    version = root.attrib.get("version")
    names: list[str] = []
    for element in root.iter():
        if element.tag.split("}")[-1] != "FeatureType":
            continue
        for child in element:
            if child.tag.split("}")[-1] == "Name" and child.text:
                names.append(child.text.strip())
                break
    return version, names


def check_catalog_source(db: Session, source: SourceRegistry) -> CatalogCheckOut:
    if source.service_type != "WFS" or not source.service_url:
        raise HTTPException(status_code=422, detail="Kontrola online jest dostępna tylko dla usług WFS")
    checked_at = datetime.now(UTC)
    started = time.perf_counter()
    try:
        response = httpx.get(
            source.service_url,
            params={"service": "WFS", "request": "GetCapabilities"},
            timeout=get_settings().wfs_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        version, names = _feature_type_names(response.content)
        expected = (source.adapter_config or {}).get("typename")
        if expected and expected not in names:
            raise ImportFailure(f"Usługa nie ogłasza oczekiwanej warstwy {expected}")
        status = "AVAILABLE"
        message = f"Usługa odpowiada i udostępnia {len(names)} warstw."
        source.last_check_status = status
        source.last_check_message = message
        source.last_checked_at = checked_at
        if source.key == "GUGIK_PRG_WFS" and expected:
            source.is_active = True
            source.implementation_status = "IMPLEMENTED"
        db.commit()
        return CatalogCheckOut(
            key=source.key,
            status=status,
            checked_at=checked_at,
            response_ms=round((time.perf_counter() - started) * 1000),
            service_version=version,
            available_layers=names,
            message=message,
        )
    except Exception as exc:
        message = f"Usługa jest obecnie niedostępna: {exc}"
        source.last_check_status = "UNAVAILABLE"
        source.last_check_message = message
        source.last_checked_at = checked_at
        if source.key == "GUGIK_PRG_WFS":
            source.is_active = False
            source.implementation_status = "TEMPORARILY_UNAVAILABLE"
        db.commit()
        return CatalogCheckOut(
            key=source.key,
            status="UNAVAILABLE",
            checked_at=checked_at,
            response_ms=round((time.perf_counter() - started) * 1000),
            message=message,
        )


def preview_catalog_import(source: SourceRegistry, bbox: list[float]) -> CatalogPreviewOut:
    if source.import_mode != "AUTOMATIC" or not source.is_active:
        raise HTTPException(status_code=422, detail="To źródło nie jest dostępne do automatycznego importu")
    config = _config(source)
    params = {**_base_params(source, bbox), "resultType": "hits"}
    try:
        response = httpx.get(
            source.service_url,
            params=params,
            timeout=get_settings().wfs_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        raw_count = root.attrib.get(str(config.get("hits_attribute", "numberMatched")))
        estimated_count = int(raw_count) if raw_count and raw_count.isdigit() else None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nie udało się sprawdzić zakresu źródła: {exc}") from exc
    configured_limit = int(config.get("feature_limit") or get_settings().max_catalog_features)
    limit = min(get_settings().max_catalog_features, configured_limit)
    warnings: list[str] = []
    if estimated_count is None:
        warnings.append("Usługa nie podała liczby obiektów; limit zostanie sprawdzony podczas pobierania.")
    elif estimated_count == 0:
        warnings.append("W wybranym obszarze nie znaleziono obiektów.")
    elif estimated_count > limit:
        warnings.append(f"Zakres zawiera {estimated_count} obiektów i przekracza limit {limit}. Zmniejsz obszar.")
    return CatalogPreviewOut(
        source_key=source.key,
        source_name=source.name,
        bbox=bbox,
        estimated_feature_count=estimated_count,
        feature_limit=limit,
        allowed=estimated_count is None or 0 < estimated_count <= limit,
        warnings=warnings,
    )


def _page_plan(
    config: dict[str, Any], estimated_count: int | None, feature_limit: int
) -> list[tuple[int | None, int]]:
    page_size = int(config.get("page_size") or 0)
    if not page_size:
        return [(None, feature_limit + 1)]
    total = estimated_count if estimated_count is not None else feature_limit + 1
    return [
        (index * page_size, min(page_size, total - index * page_size))
        for index in range(ceil(total / page_size))
    ]


def _download_wfs(
    source: SourceRegistry,
    bbox: list[float],
    path: Path,
    *,
    start_index: int | None,
    count: int,
) -> tuple[int, str, dict[str, str]]:
    settings = get_settings()
    config = _config(source)
    params = _base_params(source, bbox)
    output_format = config.get("output_format")
    if output_format:
        params["outputFormat"] = str(output_format)
    params[str(config.get("limit_parameter", "count"))] = str(count)
    if start_index is not None:
        params[str(config.get("start_index_parameter", "startIndex"))] = str(start_index)
    digest = hashlib.sha256()
    downloaded = 0
    response_headers: dict[str, str] = {}
    with httpx.stream(
        "GET",
        source.service_url,
        params=params,
        timeout=settings.wfs_timeout_seconds,
        follow_redirects=True,
    ) as response:
        response.raise_for_status()
        response_headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"content-type", "content-length", "etag", "last-modified"}
        }
        with path.open("wb") as destination:
            for chunk in response.iter_bytes():
                downloaded += len(chunk)
                if downloaded > settings.max_wfs_mb * 1024 * 1024:
                    raise ImportFailure("Odpowiedź WFS przekracza skonfigurowany limit rozmiaru")
                digest.update(chunk)
                destination.write(chunk)
    return downloaded, digest.hexdigest(), response_headers


def import_catalog_source(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    source: SourceRegistry,
    bbox: list[float],
    layer_name: str | None,
) -> tuple[DatasetImport, Any]:
    preview = preview_catalog_import(source, bbox)
    if not preview.allowed:
        raise HTTPException(status_code=422, detail=preview.warnings[0])
    data_source, record = _create_import_records(
        db,
        project_id=project_id,
        source_name=source.name,
        source_type="WFS",
        registry_key=source.key,
        original_filename=None,
        url=source.service_url,
    )
    data_source.provider = source.provider
    data_source.description = source.description
    data_source.legal_note = source.legal_note
    logs: list[str] = []
    try:
        record.status = "RUNNING"
        record.started_at = datetime.now(UTC)
        record.metadata_json = {
            "source_catalog_key": source.key,
            "provider": source.provider,
            "service_url": source.service_url,
            "typename": (source.adapter_config or {}).get("typename"),
            "service_version": (source.adapter_config or {}).get("version"),
            "dataset_version": source.dataset_version,
            "bbox_request_wgs84": bbox,
            "preview_feature_count": preview.estimated_feature_count,
            "source_verified_at": source.last_verified_at.isoformat() if source.last_verified_at else None,
        }
        db.commit()
        config = _config(source)
        detected = str(config.get("response_format", "GML"))
        extension = ".geojson" if detected == "GeoJSON" else ".gml"
        with tempfile.TemporaryDirectory(prefix="geoharmonizer-catalog-") as temp:
            page_plan = _page_plan(
                config,
                preview.estimated_feature_count,
                get_settings().max_catalog_features,
            )
            page_metadata: list[dict[str, Any]] = []
            frames: list[gpd.GeoDataFrame] = []
            total_size = 0
            combined_digest = hashlib.sha256()
            response_headers: dict[str, str] = {}
            for page_number, (start_index, count) in enumerate(page_plan, start=1):
                path = Path(temp) / f"catalog-{page_number:03d}{extension}"
                size_bytes, page_sha256, page_headers = _download_wfs(
                    source,
                    bbox,
                    path,
                    start_index=start_index,
                    count=count,
                )
                total_size += size_bytes
                if total_size > get_settings().max_wfs_mb * 1024 * 1024:
                    raise ImportFailure("Łączna odpowiedź WFS przekracza skonfigurowany limit rozmiaru")
                with path.open("rb") as downloaded_page:
                    while chunk := downloaded_page.read(1024 * 1024):
                        combined_digest.update(chunk)
                frame = _read_vector(path, detected, logs)
                frames.append(frame)
                response_headers = response_headers or page_headers
                page_metadata.append(
                    {
                        "page": page_number,
                        "start_index": start_index,
                        "requested_count": count,
                        "received_count": len(frame),
                        "size_bytes": size_bytes,
                        "sha256": page_sha256,
                    }
                )
            if len(frames) == 1:
                gdf = frames[0]
            else:
                gdf = gpd.GeoDataFrame(
                    pd.concat(frames, ignore_index=True),
                    geometry="geometry",
                    crs=frames[0].crs,
                )
                logs.append(f"Połączono {len(frames)} stron odpowiedzi WFS.")
            gdf, detected_crs = _normalize_frame(gdf, detected, logs)
            if (
                preview.estimated_feature_count is not None
                and len(gdf) != preview.estimated_feature_count
            ):
                logs.append(
                    "Liczba obiektów w odpowiedzi GetFeature "
                    f"({len(gdf)}) różni się od wcześniejszego podglądu "
                    f"({preview.estimated_feature_count}); źródło mogło zmienić się między żądaniami."
                )
            if len(gdf) > get_settings().max_catalog_features:
                raise ImportFailure("Usługa zwróciła więcej obiektów niż dopuszcza limit katalogu")
            record = db.get(DatasetImport, record.id)
            record.detected_format = f"WFS/{detected}"
            record.detected_crs = detected_crs
            record.metadata_json = {
                **record.metadata_json,
                "download_size_bytes": total_size,
                "sha256": combined_digest.hexdigest(),
                "download_pages": page_metadata,
                "response_headers": response_headers,
                "axis_order": config.get("axis_order"),
            }
            layer = _persist_frame(
                db,
                project_id=project_id,
                dataset_import=record,
                gdf=gdf,
                layer_name=layer_name or source.name,
                layer_type=source.default_layer_type or "GENERIC_POLYGON",
                source_name=source.name,
            )
            record.status = "DONE"
            record.finished_at = datetime.now(UTC)
            record.log_text = "\n".join(["Import katalogowy WFS zakończony.", *logs])
            add_event(
                db,
                project_id=project_id,
                entity_type="dataset_import",
                entity_id=record.id,
                user_id=user_id,
                message=f"Zaimportowano źródło katalogowe „{source.name}” ({len(gdf)} obiektów).",
                details={"source_key": source.key, "warnings": logs},
            )
            db.commit()
            db.refresh(record)
            db.refresh(layer)
            return record, layer
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        record = db.get(DatasetImport, record.id)
        record.status = "ERROR"
        record.error_message = str(exc)
        record.log_text = "\n".join([*logs, f"Import katalogowy przerwany: {exc}"])
        record.finished_at = datetime.now(UTC)
        add_event(
            db,
            project_id=project_id,
            entity_type="dataset_import",
            entity_id=record.id,
            user_id=user_id,
            level="ERROR",
            message="Import katalogowy nie został zakończony.",
            details={"source_key": source.key, "reason": str(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "import_id": str(record.id)},
        ) from exc
