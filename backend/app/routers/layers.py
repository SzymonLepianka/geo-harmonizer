import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404
from app.models import DatasetImport, DataSource, Feature, Layer, User
from app.schemas import LayerOut

router = APIRouter(prefix="/api/projects/{project_id}/layers", tags=["layers"])


def _layer_dict(db: Session, layer: Layer) -> dict:
    source_name = db.scalar(
        select(DataSource.name)
        .join(DatasetImport, DatasetImport.data_source_id == DataSource.id)
        .where(DatasetImport.id == layer.dataset_import_id)
    )
    return {
        **{column.name: getattr(layer, column.name) for column in Layer.__table__.columns},
        "feature_count": db.scalar(select(func.count()).select_from(Feature).where(Feature.layer_id == layer.id)) or 0,
        "source_name": source_name,
    }


def _get_layer(project_id: uuid.UUID, layer_id: uuid.UUID, db: Session) -> Layer:
    layer = db.get(Layer, layer_id)
    if not layer or layer.project_id != project_id:
        raise HTTPException(status_code=404, detail="Nie znaleziono warstwy")
    return layer


@router.get("", response_model=list[LayerOut])
def list_layers(project_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    get_project_or_404(project_id, db)
    layers = db.scalars(select(Layer).where(Layer.project_id == project_id).order_by(Layer.created_at.desc())).all()
    return [_layer_dict(db, layer) for layer in layers]


@router.get("/{layer_id}", response_model=LayerOut)
def get_layer(project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    return _layer_dict(db, _get_layer(project_id, layer_id, db))


@router.get("/{layer_id}/features")
def layer_features(
    project_id: uuid.UUID,
    layer_id: uuid.UUID,
    bbox: str | None = None,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    _get_layer(project_id, layer_id, db)
    geom_4326 = func.ST_Transform(Feature.geom, 4326)
    query = select(
        Feature.id,
        Feature.external_id,
        Feature.source_object_id,
        Feature.attributes,
        func.ST_AsGeoJSON(geom_4326),
    ).where(Feature.layer_id == layer_id)
    if bbox:
        try:
            parts = [float(item.strip()) for item in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="BBOX musi mieć postać minLon,minLat,maxLon,maxLat") from exc
        envelope = func.ST_Transform(func.ST_MakeEnvelope(*parts, 4326), 2180)
        query = query.where(func.ST_Intersects(Feature.geom, envelope))
    rows = db.execute(query.limit(limit).offset(offset)).all()
    features = []
    for row in rows:
        features.append(
            {
                "type": "Feature",
                "id": str(row[0]),
                "geometry": json.loads(row[4]),
                "properties": {
                    "id": str(row[0]),
                    "external_id": row[1],
                    "source_object_id": row[2],
                    "attributes": row[3],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features, "numberReturned": len(features), "limit": limit, "offset": offset}


@router.get("/{layer_id}/metadata")
def layer_metadata(project_id: uuid.UUID, layer_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    layer = _get_layer(project_id, layer_id, db)
    dataset_import = db.get(DatasetImport, layer.dataset_import_id)
    source = db.get(DataSource, dataset_import.data_source_id) if dataset_import and dataset_import.data_source_id else None
    extent = db.scalar(
        select(func.ST_AsGeoJSON(func.ST_Transform(func.ST_Envelope(func.ST_Collect(Feature.geom)), 4326))).where(Feature.layer_id == layer_id)
    )
    return {
        "layer": _layer_dict(db, layer),
        "import": {
            "id": str(dataset_import.id),
            "detected_format": dataset_import.detected_format,
            "detected_crs": dataset_import.detected_crs,
            "target_crs": dataset_import.target_crs,
            "metadata": dataset_import.metadata_json,
            "log": dataset_import.log_text,
        } if dataset_import else None,
        "source": {"id": str(source.id), "name": source.name, "type": source.source_type, "url": source.url} if source else None,
        "bbox_geojson": json.loads(extent) if extent else None,
    }

